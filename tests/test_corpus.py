"""Tests for the corpus layer (chunker, vector store, search, grounding)."""

import math

from rtc.agents.delta_agent import DeltaAgent
from rtc.corpus.chunker import paper_to_chunks
from rtc.corpus.search import CorpusSearch
from rtc.corpus.vector_store import ChunkRecord, LanceDBVectorStore, SearchHit
from rtc.schemas.delta_v2 import CoreDelta, DeltaOutput
from rtc.schemas.extraction_v2 import (
    ClaimWithEvidence,
    Evidence,
    ExtractionOutput,
    MethodComponent,
    ProblemDefinition,
)


def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeEmbedder:
    """Deterministic embedder for tests (no model download)."""

    def __init__(self, mapping: dict[str, list[float]]):
        self.mapping = {k: _norm(v) for k, v in mapping.items()}

    def embed_text(self, text: str) -> list[float]:
        return self.mapping[text]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.mapping[t] for t in texts]


def _sample_extraction() -> ExtractionOutput:
    return ExtractionOutput(
        arxiv_id="2601.00001",
        title="Sample Paper",
        problem_definition=ProblemDefinition(
            statement="problem", structural_limitation="limit"
        ),
        method_components=[
            MethodComponent(name="M1", description="desc1"),
            MethodComponent(name="M2", description="desc2"),
        ],
        claims=[
            ClaimWithEvidence(claim_id="C1", text="claim one", claim_type="method"),
            ClaimWithEvidence(claim_id="C2", text="claim two", claim_type="result"),
        ],
    )


def _sample_delta() -> DeltaOutput:
    return DeltaOutput(
        arxiv_id="2601.00001",
        one_line_takeaway="takeaway text",
        core_deltas=[
            CoreDelta(
                axis="control",
                old_approach="old",
                new_approach="new",
                why_better="better",
                evidence=Evidence(quote="q", type="quote"),
            )
        ],
        when_to_use="use",
        when_not_to_use="avoid",
    )


def test_chunker():
    chunks = paper_to_chunks("2601.00001", _sample_extraction(), _sample_delta())
    types = [c[0] for c in chunks]
    # 1 takeaway + 1 delta + 2 claims = 4 chunks
    assert len(chunks) == 4
    assert types.count("takeaway") == 1
    assert types.count("delta") == 1
    assert types.count("claim") == 2
    # delta chunk text format
    delta_chunk = next(c for c in chunks if c[0] == "delta")
    assert delta_chunk[1] == "control: old -> new"
    # claim_type carried in metadata
    claim_chunk = next(c for c in chunks if c[0] == "claim")
    assert claim_chunk[2]["claim_type"] in {"method", "result"}


def test_vector_store_roundtrip(tmp_path):
    store = LanceDBVectorStore(tmp_path / "db")
    store.upsert(
        [
            ChunkRecord("a:claim:0", "A", "claim", "alpha", _norm([1, 0, 0])),
            ChunkRecord("b:claim:0", "B", "claim", "beta", _norm([0, 1, 0])),
        ]
    )
    assert store.count() == 2

    # query returns nearest first
    hits = store.query(_norm([1, 0, 0]), top_k=2)
    assert hits[0].arxiv_id == "A"

    # exclude_arxiv_id excludes self
    hits = store.query(_norm([1, 0, 0]), top_k=2, exclude_arxiv_id="A")
    assert all(h.arxiv_id != "A" for h in hits)

    # idempotent re-index: replacing A keeps total count stable
    store.upsert([ChunkRecord("a:claim:0", "A", "claim", "alpha2", _norm([1, 0, 0]))])
    assert store.count() == 2

    # reopening the same path in a fresh instance must see persisted rows
    reopened = LanceDBVectorStore(tmp_path / "db")
    assert reopened.count() == 2
    assert reopened.query(_norm([1, 0, 0]), top_k=1)[0].arxiv_id == "A"


def test_search_threshold(tmp_path):
    store = LanceDBVectorStore(tmp_path / "db")
    store.upsert(
        [
            ChunkRecord("A:claim:0", "A", "claim", "a1", _norm([1, 0, 0])),
            ChunkRecord("A:claim:1", "A", "claim", "a2", _norm([0.95, 0.05, 0])),
            ChunkRecord("B:claim:0", "B", "claim", "b1", _norm([0, 1, 0])),
        ]
    )
    embedder = FakeEmbedder({"q": [1, 0, 0]})
    search = CorpusSearch(store, embedder)

    results = search.search_related_papers("q", top_k=5, min_score=0.5)
    # B is below threshold; A deduped to a single best-chunk hit
    assert [h.arxiv_id for h in results] == ["A"]
    assert results[0].score >= 0.5

    # raising the threshold above everything yields nothing
    none = search.search_related_papers("q", top_k=5, min_score=1.1)
    assert none == []


def test_grounded_on_filter_rejects_fabricated_ids():
    related = [SearchHit("2601.11111", "delta", "t", 0.9, {})]
    filtered = DeltaAgent._filter_grounded_on(
        ["2601.11111", "9999.99999", "2601.11111"], related
    )
    # fabricated id removed, dedup applied
    assert filtered == ["2601.11111"]

    # empty related -> nothing grounded
    assert DeltaAgent._filter_grounded_on(["2601.11111"], []) == []
