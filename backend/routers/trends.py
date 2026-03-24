from fastapi import APIRouter, HTTPException, Query

from backend.data_store import cluster_lookup, load_precomputed, load_timeline
from backend.trend_logic import cluster_scope_summary, compute_timeline, filter_papers


router = APIRouter(prefix="/api/trends", tags=["trends"])


def _parse_venues(venues: str | None) -> list[str]:
    if not venues:
        return []
    return [item.strip() for item in venues.split(",") if item.strip() and item.strip() != "All"]


@router.get("/timeline")
def get_timeline(
    cluster_id: int | None = Query(default=None),
    venue: str | None = Query(default=None),
    venues: str | None = Query(default=None),
    year: int | None = Query(default=None),
):
    selected_venues = _parse_venues(venues)
    if venue is None and not selected_venues and year is None:
        if cluster_id is None:
            return load_timeline()

        papers = filter_papers()
        timeline = compute_timeline(papers, cluster_id=cluster_id)
        if cluster_id is not None and not timeline["series"]:
            raise HTTPException(status_code=404, detail="Cluster timeline not found")
        return timeline

    papers = filter_papers(venue=venue, year=year, venues=selected_venues)
    timeline = compute_timeline(papers, cluster_id=cluster_id)
    if cluster_id is not None and not timeline["series"]:
        raise HTTPException(status_code=404, detail="Cluster timeline not found")
    return timeline


@router.get("/rising")
def get_rising_clusters(limit: int = Query(default=12, ge=1, le=100)):
    data = load_precomputed("rising")
    return {"clusters": data["clusters"][:limit]}


@router.get("/likely")
def get_likely_directions(limit: int = Query(default=6, ge=1, le=50)):
    data = load_precomputed("likely")
    return {"clusters": data["clusters"][:limit]}


@router.get("/by-venue")
def get_clusters_by_venue(
    venue: str,
    year: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=500),
    venues: str | None = Query(default=None),
):
    selected_venues = _parse_venues(venues)
    papers = filter_papers(venue=venue, year=year, venues=selected_venues)
    cluster_list = [item for item in cluster_scope_summary(papers) if item.get("enabled", True)]
    trend_priority = {"hot": 4, "rising": 3, "stable": 2, "declining": 1}
    cluster_list.sort(
        key=lambda item: (
            trend_priority.get(item.get("trend_label", "stable"), 0),
            item.get("trend_score", 0),
            item.get("paper_count", 0),
            item.get("total_citations", 0),
        ),
        reverse=True,
    )
    return {"clusters": cluster_list[:limit], "venue": venue, "venues": selected_venues, "year": year, "total": len(cluster_list)}
