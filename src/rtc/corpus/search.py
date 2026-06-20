"""Search - query the corpus and surface related prior papers."""

from __future__ import annotations

from rtc.corpus.embedder import Embedder
from rtc.corpus.vector_store import SearchHit, VectorStore


class CorpusSearch:
    """Cosine search over the corpus vector store."""

    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder

    def search(
        self,
        text: str,
        top_k: int = 5,
        exclude_arxiv_id: str | None = None,
    ) -> list[SearchHit]:
        """Raw chunk-level search."""
        if not text.strip():
            return []
        vector = self.embedder.embed_text(text)
        return self.store.query(vector, top_k=top_k, exclude_arxiv_id=exclude_arxiv_id)

    def search_related_papers(
        self,
        query_text: str,
        top_k: int,
        min_score: float,
        exclude_arxiv_id: str | None = None,
    ) -> list[SearchHit]:
        """Paper-level related search.

        Keeps only hits with score >= min_score, dedups by arxiv_id (best chunk
        per paper), and returns at most top_k papers ordered by score.
        """
        if top_k <= 0 or not query_text.strip():
            return []

        # Over-fetch chunks so dedup-by-paper can still yield top_k papers.
        pool = self.search(
            query_text, top_k=top_k * 5, exclude_arxiv_id=exclude_arxiv_id
        )

        best_by_paper: dict[str, SearchHit] = {}
        for hit in pool:
            if hit.score < min_score:
                continue
            existing = best_by_paper.get(hit.arxiv_id)
            if existing is None or hit.score > existing.score:
                best_by_paper[hit.arxiv_id] = hit

        ranked = sorted(best_by_paper.values(), key=lambda h: h.score, reverse=True)
        return ranked[:top_k]
