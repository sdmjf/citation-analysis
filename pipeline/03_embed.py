"""
Step 4: Embedding 生成
支持两种模式：
  --model openrouter  使用 OpenRouter API (qwen/qwen3-embedding-8b)，本地运行无需 GPU
  --model specter2    使用 SPECTER2（sentence-transformers），推荐在 Colab GPU 上跑

输入：data/processed/papers_filtered.csv（或 papers_with_citations.csv）
输出：data/processed/embeddings.npy
       data/processed/embedding_ids.csv
"""

import os
import time
import argparse
import numpy as np
import pandas as pd
import requests
from pathlib import Path
from tqdm import tqdm

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

INPUT_CSV = PROCESSED_DIR / "papers_filtered.csv"
EMBEDDINGS_PATH = PROCESSED_DIR / "embeddings.npy"
IDS_CSV = PROCESSED_DIR / "embedding_ids.csv"

# OpenRouter 配置
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/embeddings"
OPENROUTER_MODEL = "qwen/qwen3-embedding-8b"
OPENROUTER_BATCH_SIZE = 64   # 每次请求的文本数（根据 token 限制调整）

# SPECTER2 配置
SPECTER2_MODEL = "allenai/specter2_base"
SPECTER2_FALLBACK = "sentence-transformers/all-mpnet-base-v2"
SPECTER2_BATCH_SIZE = 32


def build_texts(df: pd.DataFrame) -> list[str]:
    """拼接 title + abstract 作为 embedding 输入"""
    return (df["title"].fillna("") + " [SEP] " + df["abstract"].fillna("")).tolist()


# ── OpenRouter Embedding ──────────────────────────────────────────────────────
def embed_openrouter(texts: list[str]) -> np.ndarray:
    """
    调用 OpenRouter embeddings API，支持断点续传。
    需要设置环境变量：OPENROUTER_API_KEY
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("未设置 OPENROUTER_API_KEY 环境变量")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    all_embeddings = []
    batches = [texts[i:i + OPENROUTER_BATCH_SIZE] for i in range(0, len(texts), OPENROUTER_BATCH_SIZE)]

    for batch in tqdm(batches, desc="[Step 4] OpenRouter embedding"):
        for attempt in range(3):
            try:
                resp = requests.post(
                    OPENROUTER_URL,
                    headers=headers,
                    json={"model": OPENROUTER_MODEL, "input": batch},
                    timeout=60,
                )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 10))
                    print(f"\n  Rate limit，等待 {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                # OpenAI 兼容格式：data[i].embedding
                batch_vecs = [item["embedding"] for item in data["data"]]
                all_embeddings.extend(batch_vecs)
                time.sleep(0.2)  # 礼貌等待
                break
            except Exception as e:
                print(f"\n  请求失败 (attempt {attempt+1}): {e}")
                time.sleep(5)
        else:
            # 3次都失败，用零向量占位（断点续传时会重试）
            dim = len(all_embeddings[0]) if all_embeddings else 1536
            all_embeddings.extend([[0.0] * dim] * len(batch))

    return np.array(all_embeddings, dtype=np.float32)


# ── SPECTER2 Embedding ────────────────────────────────────────────────────────
def embed_specter2(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    try:
        print(f"[Step 4] 加载 {SPECTER2_MODEL}...")
        model = SentenceTransformer(SPECTER2_MODEL)
    except Exception as e:
        print(f"  SPECTER2 加载失败（{e}），使用备选模型")
        model = SentenceTransformer(SPECTER2_FALLBACK)

    embeddings = model.encode(
        texts,
        batch_size=SPECTER2_BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    return embeddings.astype(np.float32)


# ── 主流程 ────────────────────────────────────────────────────────────────────
def encode_papers(df: pd.DataFrame, model_type: str) -> np.ndarray:
    # 断点续传：找出未完成的论文
    done_ids: set[str] = set()
    if EMBEDDINGS_PATH.exists() and IDS_CSV.exists():
        done_ids = set(pd.read_csv(IDS_CSV)["paper_id"].tolist())
        print(f"[Step 4] 续传：已完成 {len(done_ids)} 篇，剩余 {len(df) - len(done_ids)} 篇")

    remaining = df[~df["paper_id"].isin(done_ids)].copy()

    if len(remaining) == 0:
        print("[Step 4] 所有 embedding 已完成")
        return np.load(EMBEDDINGS_PATH)

    texts = build_texts(remaining)
    print(f"[Step 4] 使用模型：{model_type}，处理 {len(texts)} 篇论文")

    if model_type == "openrouter":
        new_embeddings = embed_openrouter(texts)
    else:
        new_embeddings = embed_specter2(texts)

    # 合并旧结果
    if EMBEDDINGS_PATH.exists() and len(done_ids) > 0:
        old_embeddings = np.load(EMBEDDINGS_PATH)
        all_embeddings = np.vstack([old_embeddings, new_embeddings])
        old_ids = pd.read_csv(IDS_CSV)
        new_ids = remaining[["paper_id"]].reset_index(drop=True)
        all_ids = pd.concat([old_ids, new_ids], ignore_index=True)
    else:
        all_embeddings = new_embeddings
        all_ids = remaining[["paper_id"]].reset_index(drop=True)

    np.save(EMBEDDINGS_PATH, all_embeddings)
    all_ids.to_csv(IDS_CSV, index=False)
    print(f"[Step 4] Embedding 完成：shape={all_embeddings.shape} → {EMBEDDINGS_PATH}")
    return all_embeddings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", choices=["openrouter", "specter2"], default="openrouter",
        help="embedding 模型：openrouter（API，本地跑）或 specter2（本地模型，推荐 GPU）"
    )
    parser.add_argument("--input", default=str(INPUT_CSV), help="输入 CSV 路径")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        # 如果 filtered 不存在，尝试 with_citations
        alt = PROCESSED_DIR / "papers_with_citations.csv"
        if alt.exists():
            input_path = alt
            print(f"[Step 4] 使用 {input_path}")
        else:
            raise FileNotFoundError(f"找不到输入文件：{input_path}")

    df = pd.read_csv(input_path)
    encode_papers(df, args.model)
    print("✅ Step 4 完成")


if __name__ == "__main__":
    main()
