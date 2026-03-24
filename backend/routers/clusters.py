from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.data_store import cluster_lookup, load_cluster_papers
from backend.trend_logic import cluster_scope_summary, filter_papers


router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("")
def list_clusters(
    q: str | None = Query(default=None),
    trend_label: str | None = Query(default=None),
    sort: Literal["trend", "citations", "papers", "name"] = "trend",
    limit: int = Query(default=60, ge=1, le=500),
):
    clusters = [cluster for cluster in cluster_scope_summary(filter_papers()) if cluster.get("enabled", True)]

    if trend_label:
        clusters = [cluster for cluster in clusters if cluster.get("trend_label") == trend_label]

    if q:
        needle = q.strip().lower()
        clusters = [
            cluster
            for cluster in clusters
            if needle in cluster.get("name", "").lower() or needle in cluster.get("description", "").lower()
        ]

    trend_priority = {"hot": 4, "rising": 3, "stable": 2, "declining": 1}
    sort_key = {
        "trend": lambda item: (trend_priority.get(item.get("trend_label", "stable"), 0), item.get("trend_score", 0), item.get("total_citations", 0)),
        "citations": lambda item: (item.get("total_citations", 0), item.get("paper_count", 0)),
        "papers": lambda item: (item.get("paper_count", 0), item.get("total_citations", 0)),
        "name": lambda item: item.get("name", ""),
    }[sort]

    reverse = sort != "name"
    clusters = sorted(clusters, key=sort_key, reverse=reverse)
    return {"clusters": clusters[:limit], "total": len(clusters)}


@router.get("/{cluster_id}")
def get_cluster(cluster_id: int):
    cluster = next((item for item in cluster_scope_summary(filter_papers()) if int(item["id"]) == cluster_id), None)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@router.get("/{cluster_id}/papers")
def get_cluster_papers(
    cluster_id: int,
    limit: int = Query(default=50, ge=1, le=5000),
    venue: str | None = Query(default=None),
    venues: str | None = Query(default=None),
    year: int | None = Query(default=None),
):
    cluster = cluster_lookup().get(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    papers = load_cluster_papers(cluster_id)
    selected_venues = [item.strip() for item in (venues or "").split(",") if item.strip() and item.strip() != "All"]
    if selected_venues:
        allowed = set(selected_venues)
        papers = [paper for paper in papers if paper.get("venue") in allowed]
    elif venue and venue != "All":
        papers = [paper for paper in papers if paper.get("venue") == venue]
    if year is not None:
        papers = [paper for paper in papers if int(paper.get("year", 0)) == year]

    papers = sorted(
        papers,
        key=lambda item: (item.get("citation_count", 0), item.get("year", 0)),
        reverse=True,
    )
    return {"cluster": cluster, "papers": papers[:limit], "total": len(papers)}
