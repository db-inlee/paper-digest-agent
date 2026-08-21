"""rank_node: off is byte-identical to the legacy gatekeeper, failure falls back."""

import pytest
from rtc.agents.gatekeeper import Gatekeeper
from rtc.config import get_settings
from rtc.pipeline.skim import gate_node, rank_node
from rtc.schemas.ranking import RankedPaper, RankingOutput
from rtc.schemas.skim import BatchSkimResult, SkimSummary


def summary(arxiv_id: str, score: int = 4, category: str = "agent") -> SkimSummary:
    return SkimSummary(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        one_liner="요약",
        tags=["agent"],
        interest_score=score,
        interest_reason="reason",
        category=category,
        link=f"https://arxiv.org/abs/{arxiv_id}",
        matched_keywords=["agent"],
    )


@pytest.fixture
def batch() -> BatchSkimResult:
    """Six papers, five qualifying - the shape that made arxiv_id decide."""
    papers = [
        summary("2608.19197"),
        summary("2608.13558", score=5),
        summary("2608.16590"),
        summary("2608.17253"),
        summary("2608.18565"),
        summary("2608.14229", category="training"),  # 카테고리 탈락
    ]
    return BatchSkimResult(papers=papers, total_processed=len(papers))


@pytest.fixture
def stub_ranking(monkeypatch):
    def install(result):
        class _Stub:
            async def generate_structured(self, **kwargs):
                if isinstance(result, Exception):
                    raise result
                return result

            def __call__(self, *a, **k):
                return self

        monkeypatch.setattr(
            "rtc.agents.ranking_agent.get_llm_client", lambda **kw: _Stub()
        )

    return install


def explode(*args, **kwargs):
    raise AssertionError("LLM must not be called")


# --- off toggle ------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_off_matches_gatekeeper(batch, monkeypatch):
    """Off must reproduce the legacy selection exactly, not just closely."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ranking_enabled", False)

    gated = await gate_node({"skim_result": batch})
    ranked = await rank_node({"skim_result": batch, "run_date": "2026-08-21"})

    legacy = await Gatekeeper(
        interest_threshold=settings.skim_interest_threshold,
        max_deep_papers=settings.max_deep_papers_per_day,
    ).run(batch)

    assert ranked == {}
    assert gated["deep_candidates"] == legacy.deep_candidates
    assert "ranking" not in ranked and "ranking_method" not in ranked


@pytest.mark.asyncio
async def test_ranking_off_does_not_call_the_llm(batch, monkeypatch):
    monkeypatch.setattr(get_settings(), "ranking_enabled", False)
    monkeypatch.setattr("rtc.agents.ranking_agent.get_llm_client", explode)

    assert await rank_node({"skim_result": batch, "run_date": "2026-08-21"}) == {}


# --- on: overwrite only on success ----------------------------------------


@pytest.mark.asyncio
async def test_ranking_overwrites_deep_candidates_on_success(batch, monkeypatch, stub_ranking):
    monkeypatch.setattr(get_settings(), "ranking_enabled", True)
    # Legacy order would be 13558(5점), then 16590/17253 by arxiv_id.
    stub_ranking(
        RankingOutput(
            ranked=[
                RankedPaper(arxiv_id=a, rank=i, reason=f"이유 {a}")
                for i, a in enumerate(
                    ["2608.19197", "2608.18565", "2608.13558", "2608.16590", "2608.17253"], 1
                )
            ]
        )
    )

    out = await rank_node({"skim_result": batch, "run_date": "2026-08-21"})

    assert out["deep_candidates"] == ["2608.19197", "2608.18565", "2608.13558"]
    assert out["ranking_method"] == "llm"
    assert len(out["ranking"]) == 5


@pytest.mark.asyncio
async def test_ranking_never_ranks_a_category_reject(batch, monkeypatch, stub_ranking):
    """The pool comes from gatekeeper's filter, so 'training' cannot appear."""
    monkeypatch.setattr(get_settings(), "ranking_enabled", True)
    stub_ranking(
        RankingOutput(
            ranked=[
                RankedPaper(arxiv_id=a, rank=i, reason="r")
                for i, a in enumerate(
                    ["2608.13558", "2608.16590", "2608.17253", "2608.18565", "2608.19197"], 1
                )
            ]
        )
    )

    out = await rank_node({"skim_result": batch, "run_date": "2026-08-21"})

    assert "2608.14229" not in {entry.arxiv_id for entry in out["ranking"]}


# --- fallback --------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_failure_leaves_gatekeeper_selection(batch, monkeypatch, stub_ranking):
    monkeypatch.setattr(get_settings(), "ranking_enabled", True)
    stub_ranking(RuntimeError("api down"))

    out = await rank_node({"skim_result": batch, "run_date": "2026-08-21"})

    assert out["ranking_method"] == "fallback"
    assert "deep_candidates" not in out  # gate가 채운 값이 그대로 남는다
    assert out["errors"][0]["node"] == "rank"


@pytest.mark.asyncio
async def test_unsound_ranking_leaves_gatekeeper_selection(batch, monkeypatch, stub_ranking):
    monkeypatch.setattr(get_settings(), "ranking_enabled", True)
    stub_ranking(RankingOutput(ranked=[RankedPaper(arxiv_id="2608.13558", rank=1, reason="r")]))

    out = await rank_node({"skim_result": batch, "run_date": "2026-08-21"})

    assert out["ranking_method"] == "fallback"
    assert "deep_candidates" not in out


@pytest.mark.asyncio
async def test_too_few_candidates_skips_ranking(monkeypatch):
    monkeypatch.setattr(get_settings(), "ranking_enabled", True)
    monkeypatch.setattr("rtc.agents.ranking_agent.get_llm_client", explode)
    single = BatchSkimResult(papers=[summary("2608.13558")], total_processed=1)

    assert await rank_node({"skim_result": single, "run_date": "2026-08-21"}) == {}


@pytest.mark.asyncio
async def test_no_skim_result_is_a_no_op(monkeypatch):
    monkeypatch.setattr(get_settings(), "ranking_enabled", True)
    monkeypatch.setattr("rtc.agents.ranking_agent.get_llm_client", explode)

    assert await rank_node({"run_date": "2026-08-21"}) == {}


# --- gatekeeper contract ---------------------------------------------------


@pytest.mark.asyncio
async def test_gatekeeper_exposes_the_qualified_pool(batch):
    result = await Gatekeeper(4, 3).run(batch)

    assert [p.arxiv_id for p in result.qualified] == [
        "2608.13558",
        "2608.16590",
        "2608.17253",
        "2608.18565",
        "2608.19197",
    ]
    assert result.filtered_count == len(result.qualified)
    assert result.deep_candidates == [p.arxiv_id for p in result.qualified][:3]
