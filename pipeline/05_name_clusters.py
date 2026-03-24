"""
Step 6: 使用 Claude API 为每个 cluster 命名
输入：data/processed/papers_clustered.csv
输出：data/processed/cluster_names.json
"""

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

CLUSTERED_CSV = PROCESSED_DIR / "papers_clustered.csv"
OUTPUT_JSON = PROCESSED_DIR / "cluster_names.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
OPENROUTER_URL = os.environ.get("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")

NAMING_PROMPT = """你是一位 NLP/AI 领域的专家研究员。
以下是同一研究方向的论文标题（按引用数从高到低排列）：

{titles}

请完成以下任务：
1. 用 3-6 个词给出这个研究方向的**名称**（优先英文）
2. 用 1-2 句话描述这个研究方向的核心内容
3. 判断这个方向是否属于 LLM/NLP 研究（是/否）

返回严格的 JSON 格式，不要有其他内容：
{{
  "name": "研究方向名称",
  "description": "一两句话描述",
  "is_nlp_related": true/false
}}"""


def build_payload(titles: str) -> tuple[str, dict, dict]:
    prompt = NAMING_PROMPT.format(titles=titles)
    if ANTHROPIC_API_KEY:
        return (
            "anthropic",
            {
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            {
                "model": ANTHROPIC_MODEL,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
        )

    if OPENROUTER_API_KEY:
        return (
            "openrouter",
            {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            {
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "reasoning": {"enabled": False},
            },
        )

    raise RuntimeError("Missing API key: set ANTHROPIC_API_KEY or OPENROUTER_API_KEY before naming clusters.")


def extract_json(text: str) -> dict:
    if isinstance(text, list):
        parts = []
        for item in text:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        text = "".join(parts)
    if text is None:
        raise json.JSONDecodeError("Empty response content", "", 0)
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.strip().startswith("```")).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start : end + 1])


def request_naming_result(titles: str) -> dict:
    provider, headers, payload = build_payload(titles)
    if provider == "anthropic":
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return extract_json(text)

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    if "choices" not in data or not data["choices"]:
        raise ValueError(f"OpenRouter unexpected response: {json.dumps(data)[:500]}")
    message = data["choices"][0]["message"]
    text = message.get("content")
    if text is None and "reasoning" in message:
        text = message["reasoning"]
    return extract_json(text)


def name_cluster(cluster_df: pd.DataFrame, top_k=25) -> dict:
    top_papers = cluster_df.nlargest(top_k, "citation_count")
    titles = "\n".join(f"- {t}" for t in top_papers["title"].tolist())

    for attempt in range(3):
        try:
            return request_naming_result(titles)
        except json.JSONDecodeError:
            print(f"  JSON 解析失败，重试 {attempt+1}/3")
            time.sleep(2)
        except ValueError as exc:
            print(f"  API 返回格式异常，重试 {attempt+1}/3: {exc}")
            time.sleep(5)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "?"
            print(f"  API 请求失败（HTTP {status_code}），重试 {attempt+1}/3")
            time.sleep(10 if status_code == 429 else 3)
        except requests.RequestException as exc:
            print(f"  网络请求异常，重试 {attempt+1}/3: {exc}")
            time.sleep(5)
    return {
        "name": f"Cluster_{cluster_df['cluster_id'].iloc[0]}",
        "description": "",
        "is_nlp_related": True,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-new", action="store_true", help="只对尚未命名的 cluster 命名")
    args = parser.parse_args()

    df = pd.read_csv(CLUSTERED_CSV)
    cluster_ids = sorted(df[df["cluster_id"] != -1]["cluster_id"].unique())

    # 断点续传
    existing = {}
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON) as f:
            existing = json.load(f)

    if args.only_new:
        cluster_ids = [c for c in cluster_ids if str(c) not in existing]
        print(f"[Step 6] 只命名新 cluster：{len(cluster_ids)} 个")

    results = dict(existing)
    provider = "Anthropic" if ANTHROPIC_API_KEY else "OpenRouter" if OPENROUTER_API_KEY else None
    if not provider:
        raise RuntimeError("Missing API key: set ANTHROPIC_API_KEY or OPENROUTER_API_KEY.")
    print(f"[Step 6] 命名提供方：{provider}")

    for cid in cluster_ids:
        if str(cid) in results and not args.only_new:
            continue
        cluster_df = df[df["cluster_id"] == cid]
        print(f"[Step 6] 命名 cluster {cid}（{len(cluster_df)} 篇）...", end=" ")

        # 保存质心用于后续 ID 对齐
        if {"umap_x", "umap_y"}.issubset(cluster_df.columns):
            centroid_2d = cluster_df[["umap_x", "umap_y"]].mean().tolist()
        else:
            centroid_2d = None

        result = name_cluster(cluster_df)
        result["cluster_id"] = int(cid)
        result["paper_count"] = len(cluster_df)
        result["enabled"] = result.get("is_nlp_related", True)
        result["centroid_2d"] = centroid_2d
        results[str(cid)] = result
        print(f"→ {result['name']}")

        # 每次保存（防止中断丢失）
        with open(OUTPUT_JSON, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(0.5)

    print(f"\n[Step 6] 命名完成：{len(results)} 个 cluster")
    print(f"  ⚠️  请手动检查 {OUTPUT_JSON}")
    print(f"     将 is_nlp_related=false 的 cluster 的 enabled 字段改为 false")
    print(f"✅ Step 6 完成")


if __name__ == "__main__":
    main()
