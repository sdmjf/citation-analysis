"""Pre-compute TF-IDF search matrices with abstracts.

Saves sparse matrices and vectorizer vocabularies so the backend
can do full abstract search without loading the 94MB CSV.

Run: python -m pipeline.09_precompute_search
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STATIC_DIR = Path(__file__).resolve().parent.parent / "backend" / "static"
PAPERS_BY_CLUSTER_DIR = STATIC_DIR / "papers_by_cluster"


def load_all_papers_with_abstracts():
    """Load papers from papers_index.json and enrich with abstracts from cluster files."""
    with open(STATIC_DIR / "papers_index.json") as f:
        papers = json.load(f)["papers"]

    # Build abstract lookup from cluster files
    abstract_map = {}
    for cluster_file in sorted(PAPERS_BY_CLUSTER_DIR.glob("*.json")):
        with open(cluster_file) as f:
            cluster_papers = json.load(f)["papers"]
        for p in cluster_papers:
            if p.get("abstract"):
                abstract_map[p["paper_id"]] = p["abstract"]

    # Enrich papers with abstracts
    for paper in papers:
        paper["abstract"] = abstract_map.get(paper["paper_id"], "")

    print(f"Total papers: {len(papers)}")
    print(f"Papers with abstracts: {sum(1 for p in papers if p['abstract'])}")
    return papers


def main():
    print("Pre-computing search matrices with abstracts...")
    papers = load_all_papers_with_abstracts()

    # Build full text (title + abstract + venue) for word-level TF-IDF
    full_texts = []
    title_texts = []
    for paper in papers:
        title = str(paper.get("title", ""))
        abstract = str(paper.get("abstract", ""))
        venue = str(paper.get("venue", ""))
        full_texts.append(f"{title} {abstract} {venue}")
        title_texts.append(title)

    # Fit TF-IDF vectorizers
    print("Building word TF-IDF (title + abstract + venue)...")
    word_vectorizer = TfidfVectorizer(
        stop_words="english", max_features=8000, ngram_range=(1, 2)
    )
    word_matrix = word_vectorizer.fit_transform(full_texts)
    del full_texts

    print("Building char TF-IDF (title only)...")
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=5000
    )
    char_matrix = char_vectorizer.fit_transform(title_texts)
    del title_texts

    # Save sparse matrices
    search_dir = STATIC_DIR / "search"
    search_dir.mkdir(exist_ok=True)

    save_npz(search_dir / "word_matrix.npz", word_matrix.tocsr())
    save_npz(search_dir / "char_matrix.npz", char_matrix.tocsr())
    print(f"  word_matrix: {word_matrix.shape}, nnz={word_matrix.nnz}")
    print(f"  char_matrix: {char_matrix.shape}, nnz={char_matrix.nnz}")

    # Save vectorizer vocabularies (needed to transform queries at runtime)
    def vocab_to_json(vocab):
        return {k: int(v) for k, v in vocab.items()}

    with open(search_dir / "word_vocab.json", "w") as f:
        json.dump({"vocabulary": vocab_to_json(word_vectorizer.vocabulary_), "idf": word_vectorizer.idf_.tolist()}, f)
    with open(search_dir / "char_vocab.json", "w") as f:
        json.dump({"vocabulary": vocab_to_json(char_vectorizer.vocabulary_), "idf": char_vectorizer.idf_.tolist()}, f)

    # Save abstract lookup (paper_id -> abstract) for enriching search results
    abstract_map = {p["paper_id"]: p.get("abstract", "") for p in papers if p.get("abstract")}
    with open(search_dir / "abstracts.json", "w") as f:
        json.dump(abstract_map, f, separators=(",", ":"), ensure_ascii=False)

    # Print sizes
    for p in sorted(search_dir.glob("*")):
        print(f"  {p.name}: {p.stat().st_size / 1024 / 1024:.1f} MB")

    print("\nDone!")


if __name__ == "__main__":
    main()
