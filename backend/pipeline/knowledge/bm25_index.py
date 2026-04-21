"""BM25 keyword index for hybrid retrieval alongside ChromaDB.

Provides sparse (BM25Okapi) retrieval that complements ChromaDB's dense
vector search. Results are fused via Reciprocal Rank Fusion in the
TwoStageRetriever.

Reference: haystack BM25Okapi implementation (3 variants, Okapi is default).
"""

import json
import logging
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# Minimal English stopwords (keep index small)
_STOPWORDS = frozenset(
    "a an and are as at be by for from has he in is it its of on that the to "
    "was were will with".split()
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


class BM25Index:
    """Persistent BM25 keyword index backed by rank-bm25."""

    def __init__(self, persist_dir: str):
        self._dir = Path(persist_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict] = []
        self._tokenized_corpus: list[list[str]] = []
        self._index: BM25Okapi | None = None
        self._load()

    # ── public API ──────────────────────────────────────────────

    def add_documents(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict] | None = None,
    ) -> int:
        """Add documents to the index. Returns count added."""
        if not ids:
            return 0
        metadatas = metadatas or [{}] * len(ids)

        # Deduplicate: overwrite existing ids
        existing = {doc_id: i for i, doc_id in enumerate(self._ids)}
        for doc_id, text, meta in zip(ids, texts, metadatas, strict=True):
            tokenized = _tokenize(text)
            if doc_id in existing:
                idx = existing[doc_id]
                self._texts[idx] = text
                self._metadatas[idx] = meta
                self._tokenized_corpus[idx] = tokenized
            else:
                self._ids.append(doc_id)
                self._texts.append(text)
                self._metadatas.append(meta)
                self._tokenized_corpus.append(tokenized)

        self._rebuild_index()
        self._save()
        return len(ids)

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Query the BM25 index. Returns [{id, text, score, metadata}]."""
        if self._index is None or not self._ids:
            return []

        tokenized_query = _tokenize(query_text)
        if not tokenized_query:
            return []

        scores = self._index.get_scores(tokenized_query)

        # Build (index, score) pairs, apply metadata filter
        candidates = []
        for i, score in enumerate(scores):
            if score <= 0:
                continue
            if filter_metadata:
                meta = self._metadatas[i]
                if not all(meta.get(k) == v for k, v in filter_metadata.items()):
                    continue
            candidates.append((i, float(score)))

        candidates.sort(key=lambda x: x[1], reverse=True)
        top = candidates[:n_results]

        return [
            {
                "id": self._ids[i],
                "text": self._texts[i],
                "score": score,
                "metadata": self._metadatas[i],
            }
            for i, score in top
        ]

    def delete(self, doc_ids: list[str]) -> int:
        """Remove documents by ID. Returns count removed."""
        id_set = set(doc_ids)
        keep = [(i, d) for i, d in enumerate(self._ids) if d not in id_set]
        if len(keep) == len(self._ids):
            return 0

        removed = len(self._ids) - len(keep)
        indices = [i for i, _ in keep]
        self._ids = [self._ids[i] for i in indices]
        self._texts = [self._texts[i] for i in indices]
        self._metadatas = [self._metadatas[i] for i in indices]
        self._tokenized_corpus = [self._tokenized_corpus[i] for i in indices]

        self._rebuild_index()
        self._save()
        return removed

    @property
    def doc_count(self) -> int:
        return len(self._ids)

    # ── internal ────────────────────────────────────────────────

    def _rebuild_index(self) -> None:
        if self._tokenized_corpus:
            self._index = BM25Okapi(self._tokenized_corpus)
        else:
            self._index = None

    def _save(self) -> None:
        data = {
            "ids": self._ids,
            "texts": self._texts,
            "metadatas": self._metadatas,
            "tokenized_corpus": self._tokenized_corpus,
        }
        with open(self._dir / "bm25_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load(self) -> None:
        path = self._dir / "bm25_data.json"
        if not path.exists():
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._ids = data["ids"]
            self._texts = data["texts"]
            self._metadatas = data["metadatas"]
            self._tokenized_corpus = data["tokenized_corpus"]
            self._rebuild_index()
            logger.info("Loaded BM25 index: %d documents", len(self._ids))
        except Exception as e:
            logger.warning("Failed to load BM25 index, starting fresh: %s", e)
            self._ids, self._texts, self._metadatas, self._tokenized_corpus = [], [], [], []
