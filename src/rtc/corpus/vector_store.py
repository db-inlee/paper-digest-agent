"""Vector store abstraction with a LanceDB implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ChunkType = Literal["takeaway", "delta", "claim"]


@dataclass
class ChunkRecord:
    """A single embeddable chunk derived from a paper."""

    id: str
    arxiv_id: str
    chunk_type: ChunkType
    text: str
    vector: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchHit:
    """A single search result."""

    arxiv_id: str
    chunk_type: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    def upsert(self, items: list[ChunkRecord]) -> None:
        """Insert/replace chunks. Re-indexing an arxiv_id replaces its rows."""

    @abstractmethod
    def query(
        self,
        vector: list[float],
        top_k: int,
        exclude_arxiv_id: str | None = None,
    ) -> list[SearchHit]:
        """Cosine top-k search, optionally excluding one arxiv_id."""

    @abstractmethod
    def count(self) -> int:
        """Total number of stored chunks."""


def _escape_sql(value: str) -> str:
    """Escape a string for use inside a single-quoted SQL literal."""
    return value.replace("'", "''")


class LanceDBVectorStore(VectorStore):
    """LanceDB-backed vector store.

    Schema (inferred on first upsert):
        id, arxiv_id, chunk_type, text: str
        vector: fixed-size float list
        metadata: JSON-encoded string
    """

    def __init__(self, db_path: Path, table_name: str = "papers"):
        import lancedb

        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        self._db = lancedb.connect(str(self.db_path))
        self._table = None
        if table_name in self._existing_table_names():
            self._table = self._db.open_table(table_name)

    def _existing_table_names(self) -> list[str]:
        """Return existing table names as a plain list across lancedb versions."""
        try:
            names = self._db.list_tables()
        except AttributeError:  # older lancedb without list_tables()
            names = self._db.table_names()
        # list_tables() returns a paginated result object with a `.tables` attr.
        if hasattr(names, "tables"):
            names = names.tables
        return list(names)

    def _to_row(self, item: ChunkRecord) -> dict:
        return {
            "id": item.id,
            "arxiv_id": item.arxiv_id,
            "chunk_type": item.chunk_type,
            "text": item.text,
            "vector": item.vector,
            "metadata": json.dumps(item.metadata, ensure_ascii=False),
        }

    def upsert(self, items: list[ChunkRecord]) -> None:
        if not items:
            return

        rows = [self._to_row(it) for it in items]

        if self._table is None:
            # Create the table from the first batch (schema inference).
            self._table = self._db.create_table(self.table_name, data=rows)
            return

        # Idempotent: delete all rows for the affected arxiv_ids, then insert.
        arxiv_ids = {it.arxiv_id for it in items}
        for aid in arxiv_ids:
            self._table.delete(f"arxiv_id = '{_escape_sql(aid)}'")
        self._table.add(rows)

    def query(
        self,
        vector: list[float],
        top_k: int,
        exclude_arxiv_id: str | None = None,
    ) -> list[SearchHit]:
        if self._table is None or top_k <= 0:
            return []

        search = self._table.search(vector).metric("cosine").limit(top_k)
        if exclude_arxiv_id:
            search = search.where(
                f"arxiv_id != '{_escape_sql(exclude_arxiv_id)}'", prefilter=True
            )

        results = search.to_list()
        hits: list[SearchHit] = []
        for r in results:
            # cosine distance -> similarity (vectors are normalized).
            distance = r.get("_distance", 0.0)
            score = 1.0 - distance
            try:
                metadata = json.loads(r.get("metadata") or "{}")
            except (json.JSONDecodeError, TypeError):
                metadata = {}
            hits.append(
                SearchHit(
                    arxiv_id=r["arxiv_id"],
                    chunk_type=r["chunk_type"],
                    text=r["text"],
                    score=score,
                    metadata=metadata,
                )
            )
        return hits

    def count(self) -> int:
        if self._table is None:
            return 0
        return self._table.count_rows()
