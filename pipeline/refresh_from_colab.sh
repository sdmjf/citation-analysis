#!/bin/bash
# Sync new clustering outputs downloaded from Colab and rebuild downstream artifacts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

SRC_CLUSTERED="data/papers_clustered.csv"
SRC_LABELS="data/cluster_labels.npy"
DST_DIR="data/processed"

if [ ! -f "$SRC_CLUSTERED" ]; then
  echo "Missing $SRC_CLUSTERED"
  exit 1
fi

if [ ! -f "$SRC_LABELS" ]; then
  echo "Missing $SRC_LABELS"
  exit 1
fi

mkdir -p "$DST_DIR"

cp "$SRC_CLUSTERED" "$DST_DIR/papers_clustered.csv"
cp "$SRC_LABELS" "$DST_DIR/cluster_labels.npy"

echo "Copied new Colab outputs into $DST_DIR"

if [ "${RENAME_CLUSTERS:-0}" = "1" ]; then
  echo "Removing old cluster naming files before full renaming..."
  rm -f data/processed/cluster_names.json data/processed/cluster_summary.json
fi

python3 pipeline/06_compute_metrics.py
python3 pipeline/07_export_api_data.py

echo "Refresh complete."
echo "If cluster ids changed significantly, rerun naming:"
echo "  OPENROUTER_API_KEY=... OPENROUTER_MODEL=... python3 pipeline/05_name_clusters.py"
