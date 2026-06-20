"""Corpus layer - local vector store and corpus search for delta grounding."""

from rtc.corpus.chunker import paper_to_chunks
from rtc.corpus.embedder import Embedder, get_embedder
from rtc.corpus.indexer import CorpusIndexer, backfill_from_reports
from rtc.corpus.search import CorpusSearch
from rtc.corpus.vector_store import (
    ChunkRecord,
    LanceDBVectorStore,
    SearchHit,
    VectorStore,
)

__all__ = [
    "Embedder",
    "get_embedder",
    "ChunkRecord",
    "SearchHit",
    "VectorStore",
    "LanceDBVectorStore",
    "paper_to_chunks",
    "CorpusIndexer",
    "backfill_from_reports",
    "CorpusSearch",
]
