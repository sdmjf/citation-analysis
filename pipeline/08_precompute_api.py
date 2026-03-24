"""Pre-compute API responses as static JSON files.

This eliminates the need to load the 94MB papers_clustered.csv at runtime,
keeping memory usage under 512MB for free-tier hosting.

Run: python -m pipeline.08_precompute_api
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.data_store import load_clusters, load_full_papers, load_papers_index, load_timeline
from backend.trend_logic import cluster_scope_summary, compute_timeline, filter_papers

STATIC_DIR = Path(__file__).resolve().parent.parent / "backend" / "static"


def save_json(data, filename):
    path = STATIC_DIR / filename
    with path.open("w") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    print(f"  {filename}: {path.stat().st_size / 1024:.0f} KB")


def main():
    print("Pre-computing API responses...")

    # 1. Cluster scope summary (used by /api/clusters, /api/trends/likely, /api/trends/rising)
    papers = filter_papers()
    all_summaries = [c for c in cluster_scope_summary(papers) if c.get("enabled", True)]

    # /api/clusters (sorted by trend)
    trend_priority = {"hot": 4, "rising": 3, "stable": 2, "declining": 1}
    clusters_sorted = sorted(
        all_summaries,
        key=lambda item: (
            trend_priority.get(item.get("trend_label", "stable"), 0),
            item.get("trend_score", 0),
            item.get("total_citations", 0),
        ),
        reverse=True,
    )
    save_json({"clusters": clusters_sorted, "total": len(clusters_sorted)}, "clusters_precomputed.json")

    # /api/trends/likely
    def likely_score(item):
        trend = float(item.get("trend_score", 0))
        citations = float(item.get("total_citations", 0))
        p = float(item.get("paper_count", 0))
        return trend * 0.65 + min(citations / 5000.0, 1.0) * 0.2 + min(p / 400.0, 1.0) * 0.15

    likely = sorted(all_summaries, key=likely_score, reverse=True)
    save_json({"clusters": likely[:12]}, "likely_precomputed.json")

    # /api/trends/rising
    rising = sorted(
        all_summaries,
        key=lambda item: (
            trend_priority.get(item.get("trend_label", "stable"), 0),
            item.get("trend_score", 0),
            item.get("paper_count", 0),
        ),
        reverse=True,
    )
    save_json({"clusters": rising[:20]}, "rising_precomputed.json")

    # 2. Venues list (used by /api/papers/venues)
    papers_index = load_papers_index()
    venue_map: dict[str, set[int]] = {}
    for paper in papers_index:
        venue = paper.get("venue")
        year = paper.get("year")
        if not venue or year is None:
            continue
        venue_map.setdefault(str(venue), set()).add(int(year))
    venues = [
        {"venue": venue, "years": sorted(years)}
        for venue, years in sorted(venue_map.items(), key=lambda item: item[0])
    ]
    save_json({"venues": venues}, "venues_precomputed.json")

    # 3. Full timeline (used by /api/trends/timeline without filters)
    # Already exists as timeline.json, but re-save to be safe
    print("\nDone! These files are served directly by the lightweight backend.")


if __name__ == "__main__":
    main()
