#!/bin/bash
# 每月增量更新脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== [$(date)] 开始增量更新 ==="

python pipeline/01_fetch_data.py --incremental
python pipeline/02_filter_llm.py
python pipeline/06_compute_metrics.py
python pipeline/07_export_api_data.py

# 读取新增论文数量
NEW_COUNT=$(python -c "import json; d=json.load(open('data/processed/update_stats.json')); print(d['new_count'])" 2>/dev/null || echo 0)
TOTAL_COUNT=$(python -c "import json; d=json.load(open('data/processed/update_stats.json')); print(d['total_count'])" 2>/dev/null || echo 1)

RATIO=$((NEW_COUNT * 100 / TOTAL_COUNT))
echo "新增论文：$NEW_COUNT / $TOTAL_COUNT（$RATIO%）"

if [ "$RATIO" -gt 5 ]; then
    echo "新增论文超过 5%，触发重新聚类..."
    python pipeline/03_embed.py --incremental
    python pipeline/04_cluster.py
    python pipeline/04b_align_cluster_ids.py
    python pipeline/05_name_clusters.py --only-new
    python pipeline/06_compute_metrics.py
    python pipeline/07_export_api_data.py
fi

echo "=== 更新完成 ==="
