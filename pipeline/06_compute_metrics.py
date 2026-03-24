"""
Step 7: 计算每个 cluster 每季度的影响力指标，以及 trend_score
输入：data/processed/papers_clustered.csv
       data/processed/cluster_names.json
输出：data/processed/quarterly_metrics.csv
       data/processed/cluster_summary.json
"""

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

CLUSTERED_CSV = PROCESSED_DIR / "papers_clustered.csv"
NAMES_JSON = PROCESSED_DIR / "cluster_names.json"
QUARTERLY_CSV = PROCESSED_DIR / "quarterly_metrics.csv"
SUMMARY_JSON = PROCESSED_DIR / "cluster_summary.json"

def compute_trend_score(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Trend Score = 近期 citation 动量 与 paper volume 动量 的平滑平均
    > 1.5 → rising, 0.8-1.5 → stable, < 0.8 → declining
    """
    results = []
    for cid, group in metrics_df.groupby("cluster_id"):
        group = group.sort_values(["year", "quarter"])
        recent = group.tail(2)

        recent_citations = recent["weighted_citations"].mean()
        historical_citations = group["weighted_citations"].mean()
        citation_momentum = (recent_citations + 1.0) / (historical_citations + 1.0)

        recent_papers = recent["paper_count"].mean()
        historical_papers = group["paper_count"].mean()
        paper_momentum = (recent_papers + 1.0) / (historical_papers + 1.0)

        trend_score = round((citation_momentum + paper_momentum) / 2.0, 3)

        if trend_score > 1.5:
            trend_label = "rising"
        elif trend_score >= 0.8:
            trend_label = "stable"
        else:
            trend_label = "declining"

        results.append({
            "cluster_id": cid,
            "trend_score": trend_score,
            "trend_label": trend_label,
        })
    return pd.DataFrame(results)


def main():
    full_df = pd.read_csv(CLUSTERED_CSV)
    full_df["period"] = full_df["year"].astype(str) + "-" + full_df["quarter"]

    with open(NAMES_JSON) as f:
        names = json.load(f)

    # 只保留 enabled=true 的 cluster
    enabled_ids = {int(k) for k, v in names.items() if v.get("enabled", True)}
    df = full_df[(full_df["cluster_id"] != -1) & (full_df["cluster_id"].isin(enabled_ids))].copy()

    # 季度指标
    records = []
    for (cluster_id, period), group in df.groupby(["cluster_id", "period"]):
        top_paper = group.nlargest(1, "citation_count").iloc[0]
        records.append({
            "cluster_id": int(cluster_id),
            "period": period,
            "year": int(period[:4]),
            "quarter": period[5:],
            "paper_count": len(group),
            "total_citations": int(group["citation_count"].sum()),
            "weighted_citations": round((group["citation_count"] * group["venue_weight"]).sum(), 2),
            "avg_citations": round(group["citation_count"].mean(), 2),
            "top_paper_id": top_paper["paper_id"],
        })

    quarterly_df = pd.DataFrame(records).sort_values(["cluster_id", "year", "quarter"]).reset_index(drop=True)
    quarterly_df.to_csv(QUARTERLY_CSV, index=False)
    print(f"[Step 7] 季度指标：{len(quarterly_df)} 行 → {QUARTERLY_CSV}")

    # cluster 汇总 + trend_score
    trend_df = compute_trend_score(quarterly_df)
    summary = {}
    for cid, group in df.groupby("cluster_id"):
        name_info = names.get(str(cid), {})
        trend_row = trend_df[trend_df["cluster_id"] == cid]
        trend_info = trend_row.iloc[0].to_dict() if not trend_row.empty else {}

        top_papers = (
            group.nlargest(10, "citation_count")[["paper_id", "title", "year", "citation_count", "url"]]
            .to_dict(orient="records")
        )
        venue_counts = group["venue"].value_counts().head(3).to_dict()
        peak_period = (
            quarterly_df[quarterly_df["cluster_id"] == cid]
            .nlargest(1, "weighted_citations")["period"]
            .values[0]
            if len(quarterly_df[quarterly_df["cluster_id"] == cid]) > 0 else ""
        )

        summary[str(cid)] = {
            "id": int(cid),
            "name": name_info.get("name", f"Cluster {cid}"),
            "description": name_info.get("description", ""),
            "enabled": bool(name_info.get("enabled", True)),
            "trend_score": float(trend_info.get("trend_score", 1.0)),
            "trend_label": trend_info.get("trend_label", "stable"),
            "total_citations": int(group["citation_count"].sum()),
            "paper_count": len(group),
            "top_papers": top_papers,
            "top_venues": venue_counts,
            "peak_period": peak_period,
            "centroid_2d": name_info.get("centroid_2d", [0, 0]),
        }

    noise_df = full_df[full_df["cluster_id"] == -1].copy()
    if not noise_df.empty:
        noise_df["period"] = noise_df["year"].astype(str) + "-" + noise_df["quarter"]
        noise_records = []
        for period, group in noise_df.groupby("period"):
            top_paper = group.nlargest(1, "citation_count").iloc[0]
            noise_records.append({
                "cluster_id": -1,
                "period": period,
                "year": int(period[:4]),
                "quarter": period[5:],
                "paper_count": len(group),
                "total_citations": int(group["citation_count"].sum()),
                "weighted_citations": round((group["citation_count"] * group["venue_weight"]).sum(), 2),
                "avg_citations": round(group["citation_count"].mean(), 2),
                "top_paper_id": top_paper["paper_id"],
            })
        noise_metrics_df = pd.DataFrame(noise_records)
        quarterly_df = (
            pd.concat([quarterly_df, noise_metrics_df], ignore_index=True)
            .sort_values(["cluster_id", "year", "quarter"])
            .reset_index(drop=True)
        )
        quarterly_df.to_csv(QUARTERLY_CSV, index=False)

        noise_trend_info = compute_trend_score(noise_metrics_df).iloc[0].to_dict()
        noise_top_papers = (
            noise_df.nlargest(10, "citation_count")[["paper_id", "title", "year", "citation_count", "url"]]
            .to_dict(orient="records")
        )
        noise_venues = noise_df["venue"].value_counts().head(3).to_dict()
        noise_peak_period = (
            noise_metrics_df.nlargest(1, "weighted_citations")["period"].values[0]
            if not noise_metrics_df.empty else ""
        )

        summary["-1"] = {
            "id": -1,
            "name": "Others",
            "description": "Papers that were not confidently assigned to a dense topic cluster by HDBSCAN. Keep this bucket to inspect edge cases, mixed topics, and emerging fragments.",
            "enabled": True,
            "trend_score": float(noise_trend_info.get("trend_score", 1.0)),
            "trend_label": noise_trend_info.get("trend_label", "stable"),
            "total_citations": int(noise_df["citation_count"].sum()),
            "paper_count": len(noise_df),
            "top_papers": noise_top_papers,
            "top_venues": noise_venues,
            "peak_period": noise_peak_period,
            "centroid_2d": None,
        }

    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[Step 7] Cluster 汇总：{len(summary)} 个 → {SUMMARY_JSON}")
    print(f"✅ Step 7 完成")


if __name__ == "__main__":
    main()
