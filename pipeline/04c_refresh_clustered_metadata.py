"""
Refresh clustered paper metadata after citation/filter updates while keeping existing cluster IDs.

Inputs:
- data/processed/papers_filtered.csv
- data/processed/papers_clustered.csv (existing cluster assignments)

Outputs:
- data/processed/papers_clustered.csv
"""

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

FILTERED_CSV = PROCESSED_DIR / "papers_filtered.csv"
CLUSTERED_CSV = PROCESSED_DIR / "papers_clustered.csv"


def main():
    filtered_df = pd.read_csv(FILTERED_CSV)
    clustered_df = pd.read_csv(CLUSTERED_CSV)

    assignment_cols = ["paper_id", "cluster_id"]
    for col in ["umap_x", "umap_y"]:
        if col in clustered_df.columns:
            assignment_cols.append(col)

    refreshed = filtered_df.merge(clustered_df[assignment_cols], on="paper_id", how="inner")

    missing = len(filtered_df) - len(refreshed)
    if missing:
        print(f"[Step 5c] Warning: {missing} filtered papers had no existing cluster assignment and were skipped.")

    refreshed.to_csv(CLUSTERED_CSV, index=False)
    print(f"[Step 5c] Refreshed clustered metadata → {CLUSTERED_CSV} ({len(refreshed)} rows)")


if __name__ == "__main__":
    main()
