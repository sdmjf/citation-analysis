import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import load_npz
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
def load_precomputed(name: str) -> Any:
    return _load_json(STATIC_DIR / f"{name}_precomputed.json")


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
    """Load papers from papers_index.json (lightweight, no abstract)."""
    return load_papers_index()


@lru_cache(maxsize=1)
def _load_search_vocab(name: str) -> dict[str, Any]:
    with (STATIC_DIR / "search" / f"{name}_vocab.json").open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_text_search_assets():
    """Load pre-computed TF-IDF matrices (built with abstracts) from disk."""
    search_dir = STATIC_DIR / "search"
    papers = load_papers_index()

    word_matrix = load_npz(search_dir / "word_matrix.npz").tocsr()
    char_matrix = load_npz(search_dir / "char_matrix.npz").tocsr()

    # Reconstruct vectorizers from saved vocabularies
    word_data = _load_search_vocab("word")
    word_vectorizer = TfidfVectorizer(stop_words="english", max_features=8000, ngram_range=(1, 2))
    word_vectorizer.vocabulary_ = word_data["vocabulary"]
    word_vectorizer.idf_ = np.array(word_data["idf"])
    word_vectorizer._tfidf._idf_diag = __import__("scipy").sparse.diags(word_vectorizer.idf_)

    char_data = _load_search_vocab("char")
    char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=5000)
    char_vectorizer.vocabulary_ = char_data["vocabulary"]
    char_vectorizer.idf_ = np.array(char_data["idf"])
    char_vectorizer._tfidf._idf_diag = __import__("scipy").sparse.diags(char_vectorizer.idf_)

    return papers, word_vectorizer, char_vectorizer, word_matrix, char_matrix


def get_abstract(paper_id: str, cluster_id: int) -> str:
    """Fetch abstract for a single paper from its cluster file."""
    try:
        papers = load_cluster_papers(cluster_id)
        for p in papers:
            if p.get("paper_id") == paper_id:
                return p.get("abstract", "")
    except Exception:
        pass
    return ""
