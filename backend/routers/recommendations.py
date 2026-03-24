from typing import Any

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.data_store import load_clusters, load_reduced_embeddings, paper_lookup


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class RecommendationRequest(BaseModel):
    liked_paper_ids: list[str] = Field(default_factory=list)
    liked_cluster_ids: list[int] = Field(default_factory=list)
    limit: int = Field(default=12, ge=1, le=50)


@router.post("")
def recommend_papers(payload: RecommendationRequest) -> dict[str, Any]:
    paper_map = paper_lookup()
    clusters = {int(cluster["id"]): cluster for cluster in load_clusters()}
    embeddings, ids, id_to_index = load_reduced_embeddings()

    valid_ids = [paper_id for paper_id in payload.liked_paper_ids if paper_id in id_to_index and paper_id in paper_map]
    for cluster_id in payload.liked_cluster_ids:
        cluster = clusters.get(int(cluster_id))
        if not cluster:
            continue
        seed_ids = [paper.get("paper_id") for paper in cluster.get("top_papers", []) if paper.get("paper_id") in id_to_index and paper.get("paper_id") in paper_map]
        valid_ids.extend(seed_ids[:5])
    valid_ids = list(dict.fromkeys(valid_ids))
    if not valid_ids:
        return {"papers": [], "liked_paper_ids": [], "liked_cluster_ids": []}

    liked_indices = [id_to_index[paper_id] for paper_id in valid_ids]
    liked_vecs = embeddings[liked_indices]
    target = liked_vecs.mean(axis=0)

    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(target)
    sims = np.divide(embeddings @ target, norms, out=np.zeros(len(ids)), where=norms > 0)

    candidates = []
    for idx, paper_id in enumerate(ids):
        if paper_id in valid_ids or paper_id not in paper_map:
            continue
        paper = paper_map[paper_id]
        score = float(sims[idx])
        candidates.append((score, paper))

    candidates.sort(key=lambda item: item[0], reverse=True)
    papers = []
    for score, paper in candidates[: payload.limit]:
        enriched = dict(paper)
        enriched["recommendation_score"] = round(score, 4)
        papers.append(enriched)

    return {"papers": papers, "liked_paper_ids": valid_ids, "liked_cluster_ids": payload.liked_cluster_ids}


@router.get("/similar/{paper_id}")
def similar_papers(paper_id: str, limit: int = 10) -> dict[str, Any]:
    paper_map = paper_lookup()
    embeddings, ids, id_to_index = load_reduced_embeddings()

    if paper_id not in id_to_index or paper_id not in paper_map:
        return {"papers": [], "paper_id": paper_id}

    target = embeddings[id_to_index[paper_id]]
    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(target)
    sims = np.divide(embeddings @ target, norms, out=np.zeros(len(ids)), where=norms > 0)

    candidates = []
    for idx, candidate_id in enumerate(ids):
        if candidate_id == paper_id or candidate_id not in paper_map:
            continue
        paper = dict(paper_map[candidate_id])
        paper["recommendation_score"] = round(float(sims[idx]), 4)
        candidates.append(paper)

    candidates.sort(key=lambda item: item["recommendation_score"], reverse=True)
    return {"papers": candidates[:limit], "paper_id": paper_id}
