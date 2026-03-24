"""
Step 8: 导出前端所需 JSON 文件
输入：data/processed/papers_clustered.csv
       data/processed/cluster_summary.json
       data/processed/quarterly_metrics.csv
输出：backend/static/clusters.json
       backend/static/timeline.json
       backend/static/papers_index.json       （轻量索引，含 UMAP 坐标）
       backend/static/papers_by_cluster/      （按 cluster_id 分片，按需加载）
"""

import json
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
STATIC_DIR = BASE_DIR / "backend" / "static"
PAPERS_BY_CLUSTER_DIR = STATIC_DIR / "papers_by_cluster"

CLUSTERED_CSV = PROCESSED_DIR / "papers_clustered.csv"
SUMMARY_JSON = PROCESSED_DIR / "cluster_summary.json"
QUARTERLY_CSV = PROCESSED_DIR / "quarterly_metrics.csv"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
PAPERS_BY_CLUSTER_DIR.mkdir(parents=True, exist_ok=True)


def export_clusters(summary: dict):
    clusters = []
    for cid, info in summary.items():
        # 计算相关 cluster（质心距离最近的 5 个，此处简化为占位）
        info["related_clusters"] = []
        clusters.append(info)

    # 计算 related_clusters（基于 centroid_2d 距离）
    import numpy as np
    centroids = {
        int(c["id"]): np.array(c["centroid_2d"])
        for c in clusters
        if c.get("centroid_2d") is not None
    }
    for c in clusters:
        cid = c["id"]
        if cid not in centroids:
            continue
        dists = {
            other_id: np.linalg.norm(centroids[cid] - vec)
            for other_id, vec in centroids.items()
            if other_id != cid
        }
        c["related_clusters"] = sorted(dists, key=dists.get)[:5]

    out = {"clusters": clusters}
    path = STATIC_DIR / "clusters.json"
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[Step 8] clusters.json → {path} ({len(clusters)} clusters)")


def export_timeline(quarterly_df: pd.DataFrame):
    periods = sorted(quarterly_df["period"].unique())
    series = {}
    for cid, group in quarterly_df.groupby("cluster_id"):
        period_map = {row["period"]: row for _, row in group.iterrows()}
        series[str(cid)] = [
            {
                "period": p,
                "paper_count": int(period_map[p]["paper_count"]) if p in period_map else 0,
                "weighted_citations": float(period_map[p]["weighted_citations"]) if p in period_map else 0.0,
            }
            for p in periods
        ]

    out = {"periods": list(periods), "series": series}
    path = STATIC_DIR / "timeline.json"
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"[Step 8] timeline.json → {path} ({len(periods)} periods, {len(series)} series)")


def export_papers(df: pd.DataFrame):
    # 轻量索引（供散点图使用，不含 abstract）
    index_cols = ["paper_id", "title", "year", "quarter", "venue", "cluster_id", "citation_count", "url"]
    has_umap = {"umap_x", "umap_y"}.issubset(df.columns)
    if has_umap:
        index_cols.extend(["umap_x", "umap_y"])
    index_df = df[index_cols].copy()
    if has_umap:
        index_df["umap_x"] = index_df["umap_x"].round(4)
        index_df["umap_y"] = index_df["umap_y"].round(4)

    index_records = index_df.to_dict(orient="records")
    path = STATIC_DIR / "papers_index.json"
    with open(path, "w") as f:
        json.dump({"papers": index_records}, f, ensure_ascii=False)
    print(f"[Step 8] papers_index.json → {path} ({len(index_records)} papers)")

    # 按 cluster 分片（含 abstract，供详情面板按需加载）
    full_cols = index_cols + ["abstract", "authors"]
    for cid, group in df.groupby("cluster_id"):
        records = group[full_cols].to_dict(orient="records")
        shard_path = PAPERS_BY_CLUSTER_DIR / f"{int(cid)}.json"
        with open(shard_path, "w") as f:
            json.dump({"papers": records}, f, ensure_ascii=False)
    print(f"[Step 8] papers_by_cluster/ → {PAPERS_BY_CLUSTER_DIR} ({df['cluster_id'].nunique()} shards)")


def main():
    df = pd.read_csv(CLUSTERED_CSV)
    quarterly_df = pd.read_csv(QUARTERLY_CSV)
    with open(SUMMARY_JSON) as f:
        summary = json.load(f)

    export_clusters(summary)
    export_timeline(quarterly_df)
    export_papers(df)
    print(f"✅ Step 8 完成")


if __name__ == "__main__":
    main()
