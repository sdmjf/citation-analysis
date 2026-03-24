import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PAPERS_BY_CLUSTER_DIR = STATIC_DIR / "papers_by_cluster"
DATA_DIR = BASE_DIR.parent / "data"


def _load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_clusters() -> list[dict[str, Any]]:
    return _load_json(STATIC_DIR / "clusters.json")["clusters"]


@lru_cache(maxsize=1)
def load_timeline() -> dict[str, Any]:
    return _load_json(STATIC_DIR / "timeline.json")


@lru_cache(maxsize=1)
def load_papers_index() -> list[dict[str, Any]]:
    return _load_json(STATIC_DIR / "papers_index.json")["papers"]


@lru_cache(maxsize=256)
def load_cluster_papers(cluster_id: int) -> list[dict[str, Any]]:
    return _load_json(PAPERS_BY_CLUSTER_DIR / f"{cluster_id}.json")["papers"]


def cluster_lookup() -> dict[int, dict[str, Any]]:
    return {int(cluster["id"]): cluster for cluster in load_clusters()}


@lru_cache(maxsize=1)
def paper_lookup() -> dict[str, dict[str, Any]]:
    return {paper["paper_id"]: paper for paper in load_papers_index()}


@lru_cache(maxsize=1)
def load_reduced_embeddings() -> tuple[np.ndarray, list[str], dict[str, int]]:
    embeddings = np.load(DATA_DIR / "reduced_embeddings.npy")
    ids = load_embedding_ids()
    id_to_index = {paper_id: idx for idx, paper_id in enumerate(ids)}
    return embeddings, ids, id_to_index


@lru_cache(maxsize=1)
def load_embedding_ids() -> list[str]:
    path = DATA_DIR / "embedding_ids.csv"
    with path.open() as f:
        lines = [line.strip() for line in f.readlines()[1:] if line.strip()]
    return lines


@lru_cache(maxsize=1)
def load_full_papers() -> list[dict[str, Any]]:
    path = DATA_DIR / "processed" / "papers_clustered.csv"
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


@lru_cache(maxsize=1)
def load_text_search_assets():
    papers = load_full_papers()
    full_texts = []
    title_texts = []
    for paper in papers:
        title = str(paper.get("title", ""))
        title_texts.append(title)
        full_texts.append(" ".join([title, str(paper.get("abstract", "")), str(paper.get("venue", ""))]))
    word_vectorizer = TfidfVectorizer(stop_words="english", max_features=12000, ngram_range=(1, 2))
    char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=8000)
    word_matrix = word_vectorizer.fit_transform(full_texts).tocsr()
    title_char_matrix = char_vectorizer.fit_transform(title_texts).tocsr()
    return papers, word_vectorizer, char_vectorizer, word_matrix, title_char_matrix
