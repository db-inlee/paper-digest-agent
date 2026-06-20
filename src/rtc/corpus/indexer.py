"""Indexer - embed paper chunks and upsert them into the vector store."""

from __future__ import annotations

import logging
from pathlib import Path

from rtc.corpus.chunker import paper_to_chunks
from rtc.corpus.embedder import Embedder
from rtc.corpus.vector_store import ChunkRecord, VectorStore
from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.storage.deep_store import DeepStore

logger = logging.getLogger(__name__)


class CorpusIndexer:
    """Index a single paper's chunks into the vector store."""

    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder

    def index_paper(
        self,
        arxiv_id: str,
        extraction: ExtractionOutput,
        delta: DeltaOutput,
        extra_metadata: dict | None = None,
    ) -> int:
        """Index one paper. Returns the number of chunks indexed."""
        extra_metadata = extra_metadata or {}
        chunks = paper_to_chunks(arxiv_id, extraction, delta)
        if not chunks:
            return 0

        vectors = self.embedder.embed_texts([text for _, text, _ in chunks])

        records: list[ChunkRecord] = []
        for i, ((chunk_type, text, chunk_meta), vector) in enumerate(
            zip(chunks, vectors)
        ):
            records.append(
                ChunkRecord(
                    id=f"{arxiv_id}:{chunk_type}:{i}",
                    arxiv_id=arxiv_id,
                    chunk_type=chunk_type,
                    text=text,
                    vector=vector,
                    metadata={**extra_metadata, **chunk_meta},
                )
            )

        self.store.upsert(records)
        return len(records)


def backfill_from_reports(
    reports_dir: Path,
    store: VectorStore,
    embedder: Embedder,
) -> dict:
    """Index every paper under reports_dir that has extraction.json + delta.json.

    Broken/missing folders are skipped and logged. Idempotent (re-running
    replaces each paper's rows).

    Returns a summary dict: {papers, chunks, skipped}.
    """
    reports_dir = Path(reports_dir)
    deep_store = DeepStore(reports_dir.parent, reports_dir=reports_dir)
    indexer = CorpusIndexer(store, embedder)

    papers = 0
    total_chunks = 0
    skipped = 0

    if not reports_dir.exists():
        logger.warning("reports_dir does not exist: %s", reports_dir)
        return {"papers": 0, "chunks": 0, "skipped": 0}

    for paper_dir in sorted(reports_dir.iterdir()):
        if not paper_dir.is_dir():
            continue
        if paper_dir.name == "daily" or paper_dir.name.startswith("."):
            continue

        slug = paper_dir.name
        try:
            extraction = deep_store.load_extraction(slug)
            delta = deep_store.load_delta(slug)
        except Exception as e:
            logger.warning("Skip %s: failed to load (%s)", slug, e)
            skipped += 1
            continue

        if extraction is None or delta is None:
            logger.info("Skip %s: missing extraction.json or delta.json", slug)
            skipped += 1
            continue

        try:
            n = indexer.index_paper(
                arxiv_id=extraction.arxiv_id,
                extraction=extraction,
                delta=delta,
                extra_metadata={"title": extraction.title, "slug": slug},
            )
        except Exception as e:
            logger.warning("Skip %s: indexing failed (%s)", slug, e)
            skipped += 1
            continue

        papers += 1
        total_chunks += n
        logger.info("Indexed %s: %d chunks", slug, n)

    return {"papers": papers, "chunks": total_chunks, "skipped": skipped}
