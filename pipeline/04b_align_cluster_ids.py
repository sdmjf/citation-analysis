"""
Step 5b: 增量更新时对齐新旧 Cluster ID（防止 ID 漂移）
在重新聚类后运行，将新 cluster ID 映射回历史 ID。
"""

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

CLUSTERED_CSV = PROCESSED_DIR / "papers_clustered.csv"
OLD_NAMES_JSON = PROCESSED_DIR / "cluster_names.json"  # 上次命名结果（含旧 ID）
ALIGNED_MAP_JSON = PROCESSED_DIR / "cluster_id_map.json"  # 新旧 ID 对应关系


def compute_centroids(df: pd.DataFrame, id_col="cluster_id") -> dict[int, np.ndarray]:
    """计算每个 cluster 的质心（基于 UMAP 2D 坐标）"""
    centroids = {}
    for cid, group in df[df[id_col] != -1].groupby(id_col):
        centroids[int(cid)] = group[["umap_x", "umap_y"]].mean().values
    return centroids


def align_ids(old_centroids: dict, new_centroids: dict) -> dict[int, int]:
    """
    匈牙利算法近似：贪心匹配新旧 cluster
    返回 {new_id: old_id}
    """
    old_ids = list(old_centroids.keys())
    new_ids = list(new_centroids.keys())

    old_vecs = np.array([old_centroids[i] for i in old_ids])
    new_vecs = np.array([new_centroids[i] for i in new_ids])

    sim_matrix = cosine_similarity(new_vecs, old_vecs)

    mapping = {}
    used_old = set()
    for i, new_id in enumerate(new_ids):
        scores = sim_matrix[i].copy()
        for j in used_old:
            scores[j] = -1
        best_j = int(scores.argmax())
        if scores[best_j] > 0.8:  # 相似度阈值，低于此视为全新 cluster
            mapping[new_id] = old_ids[best_j]
            used_old.add(best_j)
        else:
            mapping[new_id] = new_id  # 保留新 ID（全新方向）

    return mapping


def main():
    import json

    if not OLD_NAMES_JSON.exists():
        print("[Step 5b] 未找到旧命名文件，跳过对齐（首次运行）")
        return

    df = pd.read_csv(CLUSTERED_CSV)
    with open(OLD_NAMES_JSON) as f:
        old_names = json.load(f)

    old_centroids = {int(k): np.array(v.get("centroid_2d", [0, 0]))
                     for k, v in old_names.items() if "centroid_2d" in v}
    new_centroids = compute_centroids(df)

    if not old_centroids:
        print("[Step 5b] 旧命名文件中无质心信息，跳过对齐")
        return

    mapping = align_ids(old_centroids, new_centroids)
    df["cluster_id"] = df["cluster_id"].map(lambda x: mapping.get(x, x))
    df.to_csv(CLUSTERED_CSV, index=False)

    with open(ALIGNED_MAP_JSON, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"[Step 5b] ID 对齐完成，映射关系 → {ALIGNED_MAP_JSON}")
    print(f"✅ Step 5b 完成")


if __name__ == "__main__":
    main()
