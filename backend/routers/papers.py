import re

import numpy as np
from fastapi import APIRouter, Query
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from backend.data_store import cluster_lookup, load_papers_index, load_text_search_assets


router = APIRouter(prefix="/api/papers", tags=["papers"])

QUERY_EXPANSIONS = {
    "llm": ["llm", "large language model", "language model"],
    "llms": ["llm", "large language model", "language model"],
    "rag": ["retrieval", "retrieval augmented generation", "generation"],
    "hallucination": ["hallucination", "faithfulness", "factuality"],
    "hallucinations": ["hallucination", "faithfulness", "factuality"],
}

STEM_SUFFIXES = (
    "ologies",
    "ology",
    "ological",
    "ologically",
    "ication",
    "ications",
    "ation",
    "ations",
    "ingly",
    "edly",
    "iness",
    "ments",
    "ment",
    "ness",
    "ities",
    "ity",
    "ings",
    "ing",
    "ical",
    "ally",
    "ed",
    "es",
    "s",
    "al",
    "ic",
)


def stem_like(token: str) -> str:
    token = token.lower()
    for suffix in STEM_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def rooted_tokens(text: str) -> list[str]:
    return [stem_like(token) for token in re.findall(r"\w+", text.lower()) if len(token) > 2]


def normalize_query(query: str) -> tuple[str, list[str]]:
    raw_tokens = [token for token in re.findall(r"\w+", query.lower()) if token not in ENGLISH_STOP_WORDS and len(token) > 2]
    expanded_terms: list[str] = []
    for token in raw_tokens:
        expanded_terms.extend(QUERY_EXPANSIONS.get(token, [token]))
    normalized = " ".join(expanded_terms)
    return normalized, expanded_terms


def _parse_venues(venues: str | None) -> list[str]:
    if not venues:
        return []
    return [item.strip() for item in venues.split(",") if item.strip() and item.strip() != "All"]


@router.get("/search")
def search_papers(
    q: str = Query(default=""),
    cluster_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    papers = load_papers_index()

    if cluster_id is not None:
        papers = [paper for paper in papers if int(paper.get("cluster_id", -1)) == cluster_id]

    if q.strip():
        needle = q.strip().lower()
        papers = [paper for paper in papers if needle in paper.get("title", "").lower()]

    papers = sorted(
        papers,
        key=lambda item: (item.get("citation_count", 0), item.get("year", 0)),
        reverse=True,
    )
    return {
        "papers": papers[:limit],
        "total": len(papers),
        "cluster": cluster_lookup().get(cluster_id) if cluster_id is not None else None,
    }


@router.get("/venues")
def list_venues():
    papers = load_papers_index()
    venue_map: dict[str, set[int]] = {}
    for paper in papers:
        venue = paper.get("venue")
        year = paper.get("year")
        if not venue or year is None:
            continue
        venue_map.setdefault(str(venue), set()).add(int(year))

    venues = [
        {"venue": venue, "years": sorted(years)}
        for venue, years in sorted(venue_map.items(), key=lambda item: item[0])
    ]
    return {"venues": venues}


@router.get("/by-venue")
def papers_by_venue(
    venue: str,
    year: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=50000),
    venues: str | None = Query(default=None),
):
    papers = load_papers_index()
    selected_venues = _parse_venues(venues)
    if selected_venues:
        allowed = set(selected_venues)
        papers = [paper for paper in papers if paper.get("venue") in allowed]
    elif venue != "All":
        papers = [paper for paper in papers if paper.get("venue") == venue]
    if year is not None:
        papers = [paper for paper in papers if int(paper.get("year", 0)) == year]

    papers = sorted(
        papers,
        key=lambda item: (item.get("citation_count", 0), item.get("year", 0)),
        reverse=True,
    )
    years = sorted({int(paper.get("year", 0)) for paper in papers if paper.get("year") is not None})
    return {"venue": venue, "venues": selected_venues, "year": year, "years": years, "papers": papers[:limit], "total": len(papers)}


@router.get("/discover")
def discover_papers(
    q: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=500),
    cluster_id: int | None = Query(default=None),
    venue: str | None = Query(default=None),
    venues: str | None = Query(default=None),
    year: int | None = Query(default=None),
    sort_by: str = Query(default="score", pattern="^(score|citations|year)$"),
):
    papers, word_vectorizer, char_vectorizer, word_matrix, title_char_matrix = load_text_search_assets()
    query = q.strip()
    if not query:
        return {"papers": [], "total": 0, "query": q}

    normalized_query, keywords = normalize_query(query)
    query_text = normalized_query or query
    query_roots = [stem_like(token) for token in re.findall(r"\w+", query_text.lower()) if len(token) > 2]
    query_root_set = set(query_roots)
    word_query_vec = word_vectorizer.transform([query_text])
    char_query_vec = char_vectorizer.transform([query_text])
    word_scores = (word_matrix @ word_query_vec.T).toarray().ravel()
    char_scores = (title_char_matrix @ char_query_vec.T).toarray().ravel()
    keyword_roots = [stem_like(token) for token in keywords]

    selected_venues = _parse_venues(venues)
    allowed_indices = []
    allowed_venues = set(selected_venues)
    for idx, paper in enumerate(papers):
        if cluster_id is not None and int(paper.get("cluster_id", -999)) != cluster_id:
            continue
        if selected_venues and str(paper.get("venue", "")) not in allowed_venues:
            continue
        if not selected_venues and venue and venue != "All" and str(paper.get("venue", "")) != venue:
            continue
        if year is not None and int(paper.get("year", 0) or 0) != year:
            continue
        allowed_indices.append(idx)

    if not allowed_indices:
        return {"papers": [], "total": 0, "query": q, "offset": offset, "limit": limit, "sort_by": sort_by}

    allowed_indices_np = np.array(allowed_indices, dtype=np.int32)
    coarse_scores = word_scores[allowed_indices_np] * 0.62 + char_scores[allowed_indices_np] * 0.38
    candidate_cap = min(max(limit * 12 + offset * 2, 160), len(allowed_indices))
    top_positions = np.argpartition(-coarse_scores, candidate_cap - 1)[:candidate_cap]
    candidate_indices = allowed_indices_np[top_positions]

    results = []
    for idx in candidate_indices.tolist():
        paper = papers[idx]
        raw_title = str(paper.get("title", ""))
        raw_abstract = str(paper.get("abstract", ""))
        title_text = raw_title.lower()
        abstract_text = raw_abstract.lower()
        exact_match = query.lower() in title_text or query.lower() == str(paper.get("paper_id", "")).lower()
        haystack = " ".join(
            [
                title_text,
                abstract_text,
                str(paper.get("venue", "")).lower(),
            ]
        )
        title_tokens = set(rooted_tokens(title_text))
        abstract_tokens = set(rooted_tokens(abstract_text))
        haystack_tokens = set(rooted_tokens(haystack))
        keyword_hits = sum(1 for token, root in zip(keywords, keyword_roots) if token in haystack or root in haystack_tokens)
        title_keyword_hits = sum(1 for token, root in zip(keywords, keyword_roots) if token in title_text or root in title_tokens)
        keyword_score = keyword_hits / max(len(keywords), 1)
        title_keyword_score = title_keyword_hits / max(len(keywords), 1)
        title_query_coverage = len(query_root_set & title_tokens) / max(len(query_root_set), 1)
        abstract_query_coverage = len(query_root_set & abstract_tokens) / max(len(query_root_set), 1)
        phrase_boost = 0.18 if normalized_query and normalized_query in title_text else 0.0
        year_value = int(paper.get("year", 0) or 0)
        recency_score = max(min((year_value - 2018) / 8, 1), 0)
        citation_score = min(np.log1p(int(paper.get("citation_count", 0))) / 8, 1)
        score = (
            float(word_scores[idx]) * 0.30
            + float(char_scores[idx]) * 0.12
            + keyword_score * 0.08
            + title_keyword_score * 0.16
            + title_query_coverage * 0.20
            + abstract_query_coverage * 0.06
            + recency_score * 0.03
            + citation_score * 0.02
            + phrase_boost
            + (0.4 if exact_match else 0.0)
        )
        if score <= 0 or (keywords and keyword_hits == 0 and title_keyword_hits == 0 and float(word_scores[idx]) < 0.03 and float(char_scores[idx]) < 0.03):
            continue

        record = {
            "paper_id": paper.get("paper_id"),
            "title": paper.get("title"),
            "year": int(paper.get("year", 0)) if paper.get("year") is not None else None,
            "quarter": paper.get("quarter"),
            "venue": paper.get("venue"),
            "cluster_id": int(paper.get("cluster_id", -1)),
            "citation_count": int(paper.get("citation_count", 0)),
            "url": paper.get("url"),
            "abstract": paper.get("abstract", ""),
            "search_score": round(score, 4),
        }
        results.append(record)

    if sort_by == "citations":
        results.sort(key=lambda item: (item["citation_count"], item["search_score"], item["year"] or 0), reverse=True)
    elif sort_by == "year":
        results.sort(key=lambda item: (item["year"] or 0, item["search_score"], item["citation_count"]), reverse=True)
    else:
        results.sort(key=lambda item: (item["search_score"], item["citation_count"], item["year"] or 0), reverse=True)
    return {
        "papers": results[offset: offset + limit],
        "total": len(results),
        "query": q,
        "offset": offset,
        "limit": limit,
        "sort_by": sort_by,
    }
