"""RankingAgent: sanity gating, deterministic shuffle, prompt assembly."""

import pytest
from rtc.agents.ranking_agent import ABSTRACT_CHAR_LIMIT, RankingAgent, RankingInput
from rtc.schemas.paper import PaperCandidate
from rtc.schemas.ranking import RankedPaper, RankingOutput
from rtc.schemas.skim import SkimSummary


def summary(arxiv_id: str, score: int = 4) -> SkimSummary:
    return SkimSummary(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        one_liner="요약",
        tags=["agent"],
        interest_score=score,
        interest_reason="reason",
        category="agent",
        link=f"https://arxiv.org/abs/{arxiv_id}",
        matched_keywords=["agent"],
    )


def candidate(arxiv_id: str, abstract: str) -> PaperCandidate:
    from datetime import datetime

    return PaperCandidate(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        abstract=abstract,
        published=datetime(2026, 8, 21),
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
    )


def ranked(ids: list[str]) -> RankingOutput:
    return RankingOutput(
        ranked=[
            RankedPaper(arxiv_id=a, rank=i, reason=f"이유 {a}")
            for i, a in enumerate(ids, 1)
        ]
    )


@pytest.fixture
def stub_llm(monkeypatch):
    """Replace the LLM with a scripted double; records the prompts it saw."""
    calls = {"count": 0, "prompt": None, "system": None}

    def install(result):
        class _Stub:
            async def generate_structured(self, prompt, output_schema, system_prompt, **kw):
                calls["count"] += 1
                calls["prompt"] = prompt
                calls["system"] = system_prompt
                calls["kwargs"] = kw
                if isinstance(result, Exception):
                    raise result
                return result

        monkeypatch.setattr(
            "rtc.agents.ranking_agent.get_llm_client", lambda **kw: _Stub()
        )
        return calls

    return install


# --- happy path ------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_returns_llm_order(stub_llm):
    calls = stub_llm(ranked(["c", "a", "b"]))
    papers = [summary("a"), summary("b"), summary("c")]

    result = await RankingAgent().run(RankingInput("2026-08-21", papers))

    assert result.ok is True
    assert result.method == "llm"
    assert result.top_ids(2) == ["c", "a"]
    assert calls["count"] == 1
    assert calls["kwargs"]["temperature"] == 0.0
    assert calls["kwargs"]["max_tokens"] == 2000


@pytest.mark.asyncio
async def test_abstract_is_joined_by_arxiv_id_and_truncated(stub_llm):
    calls = stub_llm(ranked(["a", "b"]))
    papers = [summary("a"), summary("b")]
    candidates = [candidate("a", "A" * (ABSTRACT_CHAR_LIMIT + 500)), candidate("b", "B-abstract")]

    await RankingAgent().run(RankingInput("2026-08-21", papers, candidates))

    prompt = calls["prompt"]
    assert "B-abstract" in prompt
    assert "A" * ABSTRACT_CHAR_LIMIT in prompt
    assert "A" * (ABSTRACT_CHAR_LIMIT + 1) not in prompt


@pytest.mark.asyncio
async def test_missing_abstract_does_not_break_the_prompt(stub_llm):
    stub_llm(ranked(["a", "b"]))
    result = await RankingAgent().run(
        RankingInput("2026-08-21", [summary("a"), summary("b")], [])
    )

    assert result.ok is True


# --- fallback paths --------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_falls_back(stub_llm):
    stub_llm(RuntimeError("boom"))

    result = await RankingAgent().run(
        RankingInput("2026-08-21", [summary("a"), summary("b")])
    )

    assert result.ok is False
    assert result.method == "fallback"
    assert "boom" in result.error


@pytest.mark.parametrize(
    "ids, label",
    [
        (["a"], "missing paper"),
        (["a", "b", "zz"], "hallucinated paper"),
    ],
)
@pytest.mark.asyncio
async def test_paper_set_mismatch_falls_back(stub_llm, ids, label):
    stub_llm(ranked(ids))
    papers = [summary("a"), summary("b"), summary("c")]

    result = await RankingAgent().run(RankingInput("2026-08-21", papers))

    assert result.method == "fallback", label
    assert "mismatch" in result.error


@pytest.mark.asyncio
async def test_duplicate_ranks_fall_back(stub_llm):
    stub_llm(
        RankingOutput(
            ranked=[RankedPaper(arxiv_id=a, rank=1, reason="r") for a in ("a", "b")]
        )
    )

    result = await RankingAgent().run(
        RankingInput("2026-08-21", [summary("a"), summary("b")])
    )

    assert result.method == "fallback"
    assert "1..2" in result.error


@pytest.mark.asyncio
async def test_non_contiguous_ranks_fall_back(stub_llm):
    stub_llm(
        RankingOutput(
            ranked=[
                RankedPaper(arxiv_id="a", rank=1, reason="r"),
                RankedPaper(arxiv_id="b", rank=5, reason="r"),
            ]
        )
    )

    result = await RankingAgent().run(
        RankingInput("2026-08-21", [summary("a"), summary("b")])
    )

    assert result.method == "fallback"


@pytest.mark.asyncio
async def test_single_candidate_skips_the_call(stub_llm):
    calls = stub_llm(ranked(["a"]))

    result = await RankingAgent().run(RankingInput("2026-08-21", [summary("a")]))

    assert result.method == "fallback"
    assert calls["count"] == 0


# --- shuffle ---------------------------------------------------------------


def test_shuffle_is_deterministic_per_date():
    papers = [summary(x) for x in ("a", "b", "c", "d", "e")]

    first = [p.arxiv_id for p in RankingAgent._shuffle(papers, "2026-08-21")]
    again = [p.arxiv_id for p in RankingAgent._shuffle(papers, "2026-08-21")]
    other = [p.arxiv_id for p in RankingAgent._shuffle(papers, "2026-08-22")]

    assert first == again
    assert sorted(first) == ["a", "b", "c", "d", "e"]
    assert first != other


def test_shuffle_does_not_reproduce_arxiv_id_order():
    """The whole point: prompt order must not encode the legacy tie-break."""
    papers = [summary(f"260{i}.0000{i}") for i in range(1, 8)]
    ids = [p.arxiv_id for p in papers]

    shuffled = [p.arxiv_id for p in RankingAgent._shuffle(papers, "2026-08-21")]

    assert shuffled != ids
    assert shuffled != list(reversed(ids))
