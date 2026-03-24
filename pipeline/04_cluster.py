"""
Step 5: UMAP 降维 + HDBSCAN 聚类
输入：data/processed/embeddings.npy
       data/processed/embedding_ids.csv
输出：data/processed/cluster_labels.npy
       data/processed/papers_clustered.csv

建议在 Colab 中运行（复用 Drive 挂载）
"""

import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

EMBEDDINGS_PATH = PROCESSED_DIR / "embeddings.npy"
IDS_CSV = PROCESSED_DIR / "embedding_ids.csv"
FILTERED_CSV = PROCESSED_DIR / "papers_filtered.csv"

LABELS_PATH = PROCESSED_DIR / "cluster_labels.npy"
CLUSTERED_CSV = PROCESSED_DIR / "papers_clustered.csv"

# 聚类参数（可根据实际结果调整）
UMAP_CLUSTER_COMPONENTS = 10
REFINE_MIN_CLUSTER_SIZES = [80, 40, 20]
HDBSCAN_MIN_SAMPLES = 5
TARGET_NOISE_RATIO = 0.10
RANDOM_STATE = 42


def refine_noise_clusters(reduced_embeddings: np.ndarray) -> np.ndarray:
    import hdbscan

    labels = np.full(len(reduced_embeddings), -1, dtype=int)
    pending_idx = np.arange(len(reduced_embeddings))
    next_cluster_id = 0

    for round_id, min_cluster_size in enumerate(REFINE_MIN_CLUSTER_SIZES, start=1):
        if len(pending_idx) == 0:
            break

        print(
            f"[Step 5] Round {round_id}: HDBSCAN min_cluster_size={min_cluster_size} "
            f"on {len(pending_idx)} papers"
        )
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=HDBSCAN_MIN_SAMPLES,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        round_labels = clusterer.fit_predict(reduced_embeddings[pending_idx])
        unique_labels = sorted(set(round_labels) - {-1})
        print(f"[Step 5] Round {round_id}: found {len(unique_labels)} clusters")

        for local_label in unique_labels:
            mask = round_labels == local_label
            original_idx = pending_idx[mask]
            labels[original_idx] = next_cluster_id
            next_cluster_id += 1

        pending_idx = pending_idx[round_labels == -1]
        noise_ratio = len(pending_idx) / len(reduced_embeddings)
        print(f"[Step 5] Round {round_id}: remaining Others {len(pending_idx)} ({noise_ratio:.1%})")
        if noise_ratio <= TARGET_NOISE_RATIO:
            print(f"[Step 5] Noise ratio <= {TARGET_NOISE_RATIO:.0%}, stop refining")
            break

    return labels


def run_clustering(embeddings: np.ndarray):
    import umap

    print(f"[Step 5] UMAP 降维（{embeddings.shape[1]}D → {UMAP_CLUSTER_COMPONENTS}D，用于聚类）...")
    reducer_cluster = umap.UMAP(
        n_components=UMAP_CLUSTER_COMPONENTS,
        n_neighbors=15,
        min_dist=0.0,
        metric="cosine",
        random_state=RANDOM_STATE,
    )
    reduced = reducer_cluster.fit_transform(embeddings)

    labels = refine_noise_clusters(reduced)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    noise_ratio = (labels == -1).sum() / len(labels)
    print(f"[Step 5] 聚类结果：{n_clusters} 个 cluster，噪声占比 {noise_ratio:.1%}")
    return labels


def main():
    embeddings = np.load(EMBEDDINGS_PATH)
    ids_df = pd.read_csv(IDS_CSV)
    papers_df = pd.read_csv(FILTERED_CSV)

    labels = run_clustering(embeddings)

    np.save(LABELS_PATH, labels)

    # 合并聚类结果到论文表
    ids_df["cluster_id"] = labels
    result = papers_df.merge(ids_df, on="paper_id", how="inner")
    result.to_csv(CLUSTERED_CSV, index=False)

    print(f"✅ Step 5 完成 → {CLUSTERED_CSV}")
    print(f"   cluster_labels: {LABELS_PATH}")


if __name__ == "__main__":
    main()
