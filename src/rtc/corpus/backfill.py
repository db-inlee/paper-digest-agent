"""Backfill entrypoint: index existing reports into the corpus vector store.

Usage:
    python -m rtc.corpus.backfill

Idempotent and safe to re-run.
"""

from __future__ import annotations

import logging

from rtc.config import get_settings
from rtc.corpus.embedder import get_embedder
from rtc.corpus.indexer import backfill_from_reports
from rtc.corpus.vector_store import LanceDBVectorStore


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    store = LanceDBVectorStore(settings.corpus_db_dir)
    embedder = get_embedder(settings.embedding_model)

    summary = backfill_from_reports(settings.reports_dir, store, embedder)

    print("=== Corpus Backfill Summary ===")
    print(f"Papers indexed : {summary['papers']}")
    print(f"Chunks indexed : {summary['chunks']}")
    print(f"Skipped        : {summary['skipped']}")
    print(f"Total in store : {store.count()}")
    print(f"DB path        : {settings.corpus_db_dir}")


if __name__ == "__main__":
    main()
