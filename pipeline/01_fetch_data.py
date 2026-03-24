"""
Step 1 & 2: 数据获取、清洗，以及 Semantic Scholar 批量引用数获取
使用官方 acl-anthology Python 包获取 ACL 数据。
输出：data/processed/papers_with_citations.csv
"""

import json
import os
import time
import requests
import pandas as pd
from tqdm import tqdm
from pathlib import Path
import argparse

# ── 路径配置 ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

CLEAN_CSV = PROCESSED_DIR / "papers_clean.csv"
CITATIONS_CSV = PROCESSED_DIR / "papers_with_citations.csv"
CITATIONS_CHECKPOINT_CSV = PROCESSED_DIR / "papers_with_citations.partial.csv"

# ── Venue 配置 ────────────────────────────────────────────────────────────────
DEFAULT_TARGET_VENUES = [
    "ACL", "EMNLP", "NAACL", "EACL", "COLING", "TACL", "COLM",
    "Findings of ACL", "Findings of EMNLP", "Findings of NAACL",
]

VENUE_WEIGHTS = {
    "ACL": 1.0,
    "EMNLP": 1.0,
    "NAACL": 0.9,
    "TACL": 1.0,
    "ICLR": 1.0,
    "NeurIPS": 1.0,
    "ICML": 1.0,
    "COLM": 1.0,
    "EACL": 0.8,
    "COLING": 0.8,
    "Findings of ACL": 0.7,
    "Findings of EMNLP": 0.7,
    "Findings of NAACL": 0.7,
}
DEFAULT_VENUE_WEIGHT = 0.6

# ── Semantic Scholar 配置 ─────────────────────────────────────────────────────
S2_BATCH_API = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
S2_BATCH_SIZE = 100


# ── Venue acronym → 规范名 映射 ───────────────────────────────────────────────
# key 为 Venue.acronym.lower()，value 为我们使用的规范名
ACRONYM_TO_VENUE = {
    "acl": "ACL",
    "emnlp": "EMNLP",
    "naacl": "NAACL",
    "eacl": "EACL",
    "coling": "COLING",
    "tacl": "TACL",
    "colm": "COLM",
    "iclr": "ICLR",
    "neurips": "NeurIPS",
    "icml": "ICML",
}

# Findings 的 venue_id 是 "findings"，需要根据 collection_id 判断所属会议
FINDINGS_COLLECTION_MAP = {
    "acl": "Findings of ACL",
    "emnlp": "Findings of EMNLP",
    "naacl": "Findings of NAACL",
    "eacl": "Findings of EACL",
}


def _normalize_venue_name(acronym: str) -> str:
    return ACRONYM_TO_VENUE.get(acronym, acronym.upper())


def _get_venue_from_volume(anthology, paper) -> str | None:
    """
    通过 volume.venues() 获取规范 venue 名。
    支持新格式（2022.acl-long）和旧格式（N18, D18）。
    """
    try:
        cid = paper.collection_id
        vol_id = paper.full_id_tuple[1]
        coll = anthology.collections.get(cid)
        if coll is None:
            return None
        vol = coll.get(vol_id)
        if vol is None:
            return None
        venue_list = list(vol.venues())
        if not venue_list:
            return None

        acronym = venue_list[0].acronym.lower()

        # Findings 特殊处理：需要从 collection_id 推断是哪个会议的 findings
        if acronym == "findings":
            cid_lower = str(cid).lower()
            for conf_key, conf_name in FINDINGS_COLLECTION_MAP.items():
                if conf_key in cid_lower:
                    return conf_name
            return "Findings of ACL"  # fallback

        return _normalize_venue_name(acronym)
    except Exception:
        return None


def _month_to_quarter(month) -> str:
    try:
        m = int(month)
        return f"Q{(m - 1) // 3 + 1}"
    except (TypeError, ValueError):
        return "Q3"


def parse_acl(min_year=2018, force=False, allowed_venues: set[str] | None = None) -> pd.DataFrame:
    if CLEAN_CSV.exists() and not force:
        print(f"[Step 1] 已存在 {CLEAN_CSV}，跳过解析（使用 --force-parse 重新解析）")
        return pd.read_csv(CLEAN_CSV)

    print("[Step 1] 加载 acl-anthology（首次运行会下载索引，约需 1-2 分钟）...")
    from acl_anthology import Anthology
    anthology = Anthology.from_repo()

    records = []
    all_papers = list(anthology.papers())
    print(f"[Step 1] 共发现 {len(all_papers)} 篇论文，过滤 {min_year} 年后目标 venue...")

    for paper in tqdm(all_papers, desc="解析论文"):
        # 年份过滤
        try:
            year = int(paper.year)
        except (TypeError, ValueError, AttributeError):
            continue
        if year < min_year:
            continue

        # abstract 过滤
        abstract = getattr(paper, "abstract", None)
        if not abstract or not str(abstract).strip():
            continue

        # Venue 识别（使用 volume.venues() 精确匹配）
        venue = _get_venue_from_volume(anthology, paper)
        if venue is None:
            continue
        if allowed_venues is not None and venue not in allowed_venues:
            continue

        # 作者
        try:
            authors = "; ".join(str(a) for a in paper.authors)
        except Exception:
            authors = ""

        # URL
        try:
            url = f"https://aclanthology.org/{paper.full_id}"
        except Exception:
            url = ""

        month = getattr(paper, "month", None)

        records.append({
            "paper_id": str(paper.full_id),
            "title": str(paper.title).strip(),
            "abstract": str(abstract).strip(),
            "year": year,
            "quarter": _month_to_quarter(month),
            "venue": venue,
            "venue_weight": VENUE_WEIGHTS.get(venue, DEFAULT_VENUE_WEIGHT),
            "authors": authors,
            "url": url,
        })

    df = pd.DataFrame(records)
    df.to_csv(CLEAN_CSV, index=False)
    print(f"[Step 1] 清洗完成：{len(df)} 篇论文 → {CLEAN_CSV}")
    print(df["venue"].value_counts().to_string())
    print(df["year"].value_counts().sort_index().to_string())
    return df


# ── Step 2: Semantic Scholar 批量引用数 ───────────────────────────────────────
def fetch_citations(df: pd.DataFrame, force=False) -> pd.DataFrame:
    if CITATIONS_CSV.exists() and not force:
        print(f"[Step 2] 已存在 {CITATIONS_CSV}，跳过（使用 --force-citations 重新获取）")
        return pd.read_csv(CITATIONS_CSV)

    # 断点续传：优先使用 partial checkpoint；force=True 时清空正式产物，但仍允许续传 partial。
    done_ids: set[str] = set()
    cached = None
    if CITATIONS_CHECKPOINT_CSV.exists():
        cached = pd.read_csv(CITATIONS_CHECKPOINT_CSV)
        done_ids = set(cached["paper_id"].tolist())
        print(f"[Step 2] 从 checkpoint 续传：已完成 {len(done_ids)} 篇，剩余 {len(df) - len(done_ids)} 篇")
    elif not force and CITATIONS_CSV.exists():
        cached = pd.read_csv(CITATIONS_CSV)
        done_ids = set(cached["paper_id"].tolist())
        print(f"[Step 2] 从正式文件续传：已完成 {len(done_ids)} 篇，剩余 {len(df) - len(done_ids)} 篇")

    headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
    remaining = df[~df["paper_id"].isin(done_ids)].copy()
    paper_ids = remaining["paper_id"].tolist()
    s2_ids = [f"ACL:{pid}" for pid in paper_ids]

    citation_map: dict[str, int] = {}
    id_batches = [paper_ids[i:i + S2_BATCH_SIZE] for i in range(0, len(paper_ids), S2_BATCH_SIZE)]
    s2_batches = [s2_ids[i:i + S2_BATCH_SIZE] for i in range(0, len(s2_ids), S2_BATCH_SIZE)]

    def fetch_batch(orig_ids, s2_ids):
        """获取一批论文的引用数，400 时自动降级到逐条查询。"""
        for attempt in range(3):
            try:
                resp = requests.post(
                    S2_BATCH_API,
                    params={"fields": "citationCount"},
                    json={"ids": s2_ids},
                    headers=headers,
                    timeout=30,
                )
                if resp.status_code == 429:
                    print(f"\n  Rate limit，等待 60s...")
                    time.sleep(60)
                    continue
                if resp.status_code == 400:
                    # 批次含无效 ID，拆成单条逐个查询
                    for pid, sid in zip(orig_ids, s2_ids):
                        try:
                            r = requests.post(
                                S2_BATCH_API,
                                params={"fields": "citationCount"},
                                json={"ids": [sid]},
                                headers=headers,
                                timeout=15,
                            )
                            if r.status_code == 200:
                                items = r.json()
                                citation_map[pid] = items[0].get("citationCount", 0) if items and items[0] else 0
                            else:
                                citation_map[pid] = 0
                        except Exception:
                            citation_map[pid] = 0
                        time.sleep(0.5)
                    return
                resp.raise_for_status()
                results = resp.json()
                for pid, item in zip(orig_ids, results):
                    citation_map[pid] = item.get("citationCount", 0) if item else 0
                time.sleep(1)
                return
            except Exception as e:
                print(f"\n  批次请求失败 (attempt {attempt+1}): {e}")
                time.sleep(5)

    processed_batches = 0
    for batch_orig, batch_s2 in tqdm(zip(id_batches, s2_batches), total=len(id_batches), desc="[Step 2] 获取引用数"):
        fetch_batch(batch_orig, batch_s2)
        processed_batches += 1

        if processed_batches % 10 == 0 or processed_batches == len(id_batches):
            partial = remaining[remaining["paper_id"].isin(citation_map.keys())].copy()
            partial["citation_count"] = partial["paper_id"].map(citation_map).fillna(0).astype(int)
            if cached is not None and len(cached) > 0:
                checkpoint = pd.concat([cached, partial], ignore_index=True)
                checkpoint = checkpoint.drop_duplicates(subset=["paper_id"], keep="last")
            else:
                checkpoint = partial
            checkpoint.to_csv(CITATIONS_CHECKPOINT_CSV, index=False)
            print(f"\n[Step 2] checkpoint 已保存：{len(checkpoint)} 篇 → {CITATIONS_CHECKPOINT_CSV}")

    remaining["citation_count"] = remaining["paper_id"].map(citation_map).fillna(0).astype(int)

    if cached is not None and len(done_ids) > 0:
        final = pd.concat([cached, remaining], ignore_index=True)
    else:
        final = remaining

    final = final.drop_duplicates(subset=["paper_id"], keep="last")
    final.to_csv(CITATIONS_CSV, index=False)
    if CITATIONS_CHECKPOINT_CSV.exists():
        CITATIONS_CHECKPOINT_CSV.unlink()
    print(f"[Step 2] 完成：{len(final)} 篇（含引用数）→ {CITATIONS_CSV}")
    return final


# ── 主入口 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-parse", action="store_true", help="强制重新解析 ACL 数据")
    parser.add_argument("--force-citations", action="store_true", help="强制重新获取引用数")
    parser.add_argument("--skip-citations", action="store_true", help="跳过引用数获取（用 0 占位）")
    parser.add_argument("--incremental", action="store_true", help="增量更新模式")
    parser.add_argument("--all-venues", action="store_true", help="不过滤 venue，尽可能保留 Anthology 中识别到的全部 venue")
    parser.add_argument("--venues", type=str, default="", help="逗号分隔的 venue 白名单，如 ACL,EMNLP,TACL")
    args = parser.parse_args()

    allowed_venues = None
    if args.venues.strip():
        allowed_venues = {item.strip() for item in args.venues.split(",") if item.strip()}
    elif not args.all_venues:
        allowed_venues = set(DEFAULT_TARGET_VENUES)

    df = parse_acl(force=args.force_parse, allowed_venues=allowed_venues)

    if not args.skip_citations:
        df = fetch_citations(df, force=args.force_citations)
    else:
        df["citation_count"] = 0
        df.to_csv(CITATIONS_CSV, index=False)
        print("[Step 2] 跳过引用数获取，citation_count 全部设为 0")

    print(f"\n✅ Step 1 & 2 完成 → {CITATIONS_CSV}")


if __name__ == "__main__":
    main()
