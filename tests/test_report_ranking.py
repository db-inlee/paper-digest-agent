"""Report rendering with a ranking: order, reason line, table column, parser guard."""

import pytest
from rtc.agents.daily_report_agent import (
    DailyReportAgent,
    PaperReportData,
    _sanitize_reason,
)
from rtc.schemas.ranking import RankedPaper
from rtc.schemas.scoring_v2 import ScoringOutput
from rtc.schemas.skim import SkimSummary
from rtc.storage.report_store import ReportStore
from rtc.storage.skim_store import SkimStore

parse_report = pytest.importorskip("toslack.converter").parse_report


def summary(arxiv_id: str) -> SkimSummary:
    return SkimSummary(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        one_liner=f"한줄 요약 {arxiv_id}",
        tags=["agent"],
        interest_score=4,
        interest_reason="reason",
        category="agent",
        link=f"https://arxiv.org/abs/{arxiv_id}",
        matched_keywords=["agent"],
    )


# 각 축은 0-5이므로 총점을 축 조합으로 매핑해 둔다.
SCORE_TRIPLES = {9: (3, 3, 3), 11: (4, 3, 4), 14: (5, 4, 5)}


def scoring(arxiv_id: str, total: int) -> ScoringOutput:
    practicality, codeability, signal = SCORE_TRIPLES[total]
    return ScoringOutput(
        arxiv_id=arxiv_id,
        practicality=practicality,
        codeability=codeability,
        signal=signal,
        recommendation="worth_reading",
        reasoning="근거",
        key_strength="강점",
    )


def report_data(arxiv_id: str, total: int) -> PaperReportData:
    return PaperReportData(
        slug=f"{arxiv_id}-paper",
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        skim=summary(arxiv_id),
        scoring=scoring(arxiv_id, total),
    )


@pytest.fixture
def agent(tmp_path, monkeypatch):
    instance = DailyReportAgent()
    instance.report_store = ReportStore(tmp_path / "reports")
    monkeypatch.setattr(instance.settings, "papers_base_dir", tmp_path / "papers")
    monkeypatch.setattr(instance.settings, "trend_section_enabled", False)
    return instance


RANKING = {
    "b": RankedPaper(arxiv_id="b", rank=1, reason="b는 기존 파이프라인을 구조적으로 대체한다."),
    "a": RankedPaper(arxiv_id="a", rank=2, reason="a는 재조합에 가깝다."),
}


# --- ordering --------------------------------------------------------------


def test_ranking_beats_score_for_ordering(agent):
    """Score would put 'a' first; the ranking must win."""
    papers = [report_data("a", 14), report_data("b", 9)]
    papers.sort(key=lambda p: agent._order_key(p, RANKING))

    assert [p.arxiv_id for p in papers] == ["b", "a"]


def test_unranked_papers_sort_after_ranked_ones_by_score(agent):
    """A same-date rerun leaves papers without a rank - a normal case."""
    papers = [report_data("z", 14), report_data("a", 9), report_data("b", 9)]
    papers.sort(key=lambda p: agent._order_key(p, RANKING))

    assert [p.arxiv_id for p in papers] == ["b", "a", "z"]


def test_empty_ranking_keeps_score_order(agent):
    papers = [report_data("a", 9), report_data("b", 14)]
    papers.sort(key=lambda p: agent._order_key(p, {}))

    assert [p.arxiv_id for p in papers] == ["b", "a"]


# --- selection reason line -------------------------------------------------


def test_selection_reason_line_is_rendered(agent):
    lines = agent._render_paper(1, report_data("b", 11), RANKING)
    joined = "\n".join(lines)

    assert "**선정 이유** (순위 1위): b는 기존 파이프라인을 구조적으로 대체한다." in joined


def test_no_reason_line_without_a_ranking(agent):
    assert "선정 이유" not in "\n".join(agent._render_paper(1, report_data("b", 11), None))


def test_reason_line_cannot_smuggle_parser_markers(agent):
    hostile = {
        "b": RankedPaper(
            arxiv_id="b",
            rank=1,
            reason="총점: 15/15 ⭐⭐⭐ **arXiv**: fake\n두 번째 줄",
        )
    }
    joined = "\n".join(agent._render_paper(1, report_data("b", 11), hostile))
    reason_line = [ln for ln in joined.splitlines() if ln.startswith("**선정 이유**")][0]

    assert "⭐" not in reason_line
    assert "**arXiv**:" not in reason_line
    assert "총점:" not in reason_line
    assert "두 번째 줄" in reason_line


def test_sanitizer_escapes_pipes_only_for_tables():
    assert _sanitize_reason("a | b") == "a | b"
    assert _sanitize_reason("a | b", for_table=True) == "a / b"


# --- skim table ------------------------------------------------------------


def test_table_keeps_five_columns_without_a_ranking(agent):
    lines = agent._render_skim_summary_section([summary("a")], None)

    assert lines[4].count("|") == 6  # 5열 + 양끝
    assert "선정 제외 사유" not in lines[4]


def test_reason_column_is_appended_last(agent):
    lines = agent._render_skim_summary_section([summary("a")], RANKING)
    header, row = lines[4], lines[6]

    assert header.rstrip().endswith("선정 제외 사유 |")
    assert row.rstrip().endswith("a는 재조합에 가깝다. |")
    # 한줄 요약은 여전히 다섯 번째 칸이어야 한다
    assert row.split("|")[5].strip() == "한줄 요약 a"


def test_six_column_table_still_parses_as_five(agent):
    """The notifier table regex consumes five cells; one_liner must survive."""
    section = "\n".join(agent._render_skim_summary_section([summary("a")], RANKING))
    content = f"# 2026-08-21 Daily Paper Report\n\n{section}"

    _, skim = parse_report(content)

    assert len(skim) == 1
    assert skim[0].one_liner == "한줄 요약 a"
    assert skim[0].category == "agent"


# --- end to end ------------------------------------------------------------


def test_ranking_disabled_ignores_stored_ranking(agent, monkeypatch, make_daily):
    store = SkimStore(agent.settings.base_dir, papers_dir=agent.settings.papers_dir)
    store.save(
        make_daily(
            "2026-08-21",
            ["a"],
            ["a"],
            ranking=[RankedPaper(arxiv_id="a", rank=1, reason="이유")],
            ranking_method="llm",
        )
    )

    monkeypatch.setattr(agent.settings, "ranking_enabled", True)
    assert agent._load_ranking("2026-08-21") != {}

    monkeypatch.setattr(agent.settings, "ranking_enabled", False)
    assert agent._load_ranking("2026-08-21") == {}


def test_missing_papers_dir_is_a_silent_read(agent, monkeypatch, tmp_path):
    monkeypatch.setattr(agent.settings, "papers_base_dir", tmp_path / "absent")
    monkeypatch.setattr(agent.settings, "ranking_enabled", True)

    assert agent._load_ranking("2026-08-21") == {}
    assert not (tmp_path / "absent").exists()
