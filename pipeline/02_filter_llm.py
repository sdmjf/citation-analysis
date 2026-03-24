"""
Step 3: LLM 相关论文过滤（关键词召回）
输入：data/processed/papers_with_citations.csv
输出：data/processed/papers_filtered.csv
"""

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

INPUT_CSV = PROCESSED_DIR / "papers_with_citations.csv"
OUTPUT_CSV = PROCESSED_DIR / "papers_filtered.csv"

LLM_KEYWORDS = [
    "language model", "large language model", "llm", "gpt", "bert", "transformer",
    "pre-train", "pretrain", "fine-tun", "instruction tun", "rlhf", "alignment",
    "prompt", "in-context learning", "few-shot", "zero-shot", "chain-of-thought",
    "reasoning", "text generation", "dialogue", "summarization",
    "translation", "question answering", "information extraction", "ner",
    "sentiment", "embeddings", "encoder", "decoder", "attention", "tokeniz",
    "hallucination", "rag", "retrieval augmented", "agent", "tool use",
    "multimodal", "vision language", "speech language", "generation","NLP",'natural language processing'
]


def filter_llm_papers(df: pd.DataFrame) -> pd.DataFrame:
    text = (df["title"].fillna("") + " " + df["abstract"].fillna("")).str.lower()
    pattern = "|".join(LLM_KEYWORDS)
    mask = text.str.contains(pattern, regex=True)
    filtered = df[mask].copy()
    print(f"[Step 3] 过滤前：{len(df)} 篇 → 过滤后：{len(filtered)} 篇 "
          f"（保留 {len(filtered)/len(df)*100:.1f}%）")
    return filtered


def main():
    df = pd.read_csv(INPUT_CSV)
    filtered = filter_llm_papers(df)
    filtered.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Step 3 完成 → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
