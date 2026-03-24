from collections import Counter, defaultdict
from statistics import median
from typing import Any

from backend.data_store import cluster_lookup, load_full_papers


def filter_papers(
    venue: str | None = None,
    year: int | None = None,
    venues: list[str] | None = None,
) -> list[dict[str, Any]]:
    papers = load_full_papers()
    selected_venues = [item for item in (venues or []) if item and item != "All"]
    if selected_venues:
        allowed = set(selected_venues)
        papers = [paper for paper in papers if paper.get("venue") in allowed]
    elif venue and venue != "All":
        papers = [paper for paper in papers if paper.get("venue") == venue]
    if year is not None:
        papers = [paper for paper in papers if int(paper.get("year", 0) or 0) == year]
    return papers


def cluster_scope_summary(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters = cluster_lookup()
    grouped: dict[int, dict[str, Any]] = {}
    yearly: dict[int, Counter] = defaultdict(Counter)
    venue_counts: dict[int, Counter] = defaultdict(Counter)

    for paper in papers:
        cluster_id = int(paper.get("cluster_id", -999))
        if cluster_id not in clusters:
            continue
        base = clusters[cluster_id]
        bucket = grouped.setdefault(
            cluster_id,
            {
                "id": base["id"],
                "name": base["name"],
                "description": base["description"],
                "enabled": base.get("enabled", True),
                "trend_score": 0.0,
                "trend_label": "stable",
                "paper_count": 0,
                "total_citations": 0,
                "peak_period": "",
                "top_venues": {},
                "trend_reason": "",
            },
        )
        bucket["paper_count"] += 1
        bucket["total_citations"] += int(paper.get("citation_count", 0) or 0)
        if paper.get("year"):
            yearly[cluster_id][int(paper["year"])] += 1
        if paper.get("venue"):
            venue_counts[cluster_id][str(paper["venue"])] += 1

    paper_counts = [bucket["paper_count"] for bucket in grouped.values()] or [1]
    citation_counts = [bucket["total_citations"] for bucket in grouped.values()] or [1]
    paper_median = median(paper_counts)
    citation_median = median(citation_counts)
    paper_hot_cutoff = sorted(paper_counts)[max(int(len(paper_counts) * 0.75) - 1, 0)]
    citation_hot_cutoff = sorted(citation_counts)[max(int(len(citation_counts) * 0.75) - 1, 0)]

    for cluster_id, bucket in grouped.items():
        score, label, peak_period, reason = compute_trend_label(
            year_counts=yearly[cluster_id],
            paper_count=bucket["paper_count"],
            total_citations=bucket["total_citations"],
            paper_median=paper_median,
            citation_median=citation_median,
            paper_hot_cutoff=paper_hot_cutoff,
            citation_hot_cutoff=citation_hot_cutoff,
        )
        bucket["trend_score"] = score
        bucket["trend_label"] = label
        bucket["peak_period"] = peak_period
        bucket["trend_reason"] = reason
        bucket["top_venues"] = dict(venue_counts[cluster_id].most_common(5))

    return list(grouped.values())


def compute_timeline(papers: list[dict[str, Any]], cluster_id: int | None = None) -> dict[str, Any]:
    years = [str(current_year) for current_year in sorted({int(paper.get("year", 0)) for paper in papers if paper.get("year")})]
    if not years:
        return {"cluster": None, "periods": [], "series": [] if cluster_id is not None else {}}

    totals_by_year = Counter(str(int(paper.get("year", 0))) for paper in papers if paper.get("year"))
    grouped: dict[int, Counter] = defaultdict(Counter)
    for paper in papers:
        if not paper.get("year"):
            continue
        grouped[int(paper.get("cluster_id", -1))][str(int(paper["year"]))] += 1

    if cluster_id is None:
        return {
            "periods": years,
            "series": {
                str(cid): [
                    {
                        "paper_count": grouped[cid].get(scope_year, 0),
                        "total_count": totals_by_year.get(scope_year, 0),
                        "share": grouped[cid].get(scope_year, 0) / max(totals_by_year.get(scope_year, 1), 1),
                    }
                    for scope_year in years
                ]
                for cid in grouped
            },
        }

    if cluster_id not in grouped:
        return {"cluster": None, "periods": [], "series": []}

    cluster = cluster_lookup().get(cluster_id)
    return {
        "cluster": cluster,
        "periods": years,
        "series": [
            {
                "paper_count": grouped[cluster_id].get(scope_year, 0),
                "total_count": totals_by_year.get(scope_year, 0),
                "share": grouped[cluster_id].get(scope_year, 0) / max(totals_by_year.get(scope_year, 1), 1),
            }
            for scope_year in years
        ],
    }


def compute_trend_label(
    *,
    year_counts: Counter,
    paper_count: int,
    total_citations: int,
    paper_median: float,
    citation_median: float,
    paper_hot_cutoff: int,
    citation_hot_cutoff: int,
) -> tuple[float, str, str, str]:
    years = sorted(year_counts)
    if not years:
        return 0.0, "stable", "", "No year data available."

    values = [year_counts[scope_year] for scope_year in years]
    peak_period = str(max(year_counts.items(), key=lambda item: item[1])[0])
    peak_value = max(values) or 1
    recent = sum(values[-2:]) / max(len(values[-2:]), 1)
    baseline_values = values[:-2] if len(values) > 2 else values[:-1]
    baseline = sum(baseline_values) / max(len(baseline_values), 1) if baseline_values else recent
    growth_ratio = (recent - baseline) / max(baseline, 1)
    sustain_ratio = recent / peak_value
    paper_strength = paper_count / max(paper_median, 1)
    citation_strength = total_citations / max(citation_median, 1)
    score = round(growth_ratio * 1.6 + sustain_ratio * 0.9 + min(paper_strength, 3) * 0.35 + min(citation_strength, 3) * 0.35, 2)

    if (
        paper_count >= paper_hot_cutoff
        and total_citations >= citation_hot_cutoff
        and sustain_ratio >= 0.75
    ):
        return score, "hot", peak_period, "Large, highly cited, and still operating near its peak."
    if growth_ratio >= 0.35 and recent >= max(2, baseline):
        return score, "rising", peak_period, "Recent paper output is clearly above its historical baseline."
    if paper_strength >= 1.0 and citation_strength >= 1.0 and sustain_ratio >= 0.55:
        return score, "stable", peak_period, "Large enough to matter and still maintaining recent activity."
    if growth_ratio <= -0.2 and sustain_ratio <= 0.6:
        return score, "declining", peak_period, "Recent activity is below the cluster's earlier peak."
    return score, "stable", peak_period, "The cluster remains active without a strong acceleration signal."
