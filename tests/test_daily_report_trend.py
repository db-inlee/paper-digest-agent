"""Toggling the trend section off must leave the report exactly as it was."""

import pytest
from rtc.agents.daily_report_agent import (
    DailyReportAgent,
    DailyReportInput,
    _is_iso_date,
)
from rtc.storage.report_store import ReportStore
from rtc.storage.skim_store import SkimStore

TREND_MARKER = "## 📈 트렌드 브리핑"
SECTION = "## 📈 트렌드 브리핑 (창 1일 · 1편)\n\n**키워드** (1일 1편): agent 1\n"


def body(markdown: str) -> str:
    """Drop the generated-at footer so comparisons are not clock-sensitive."""
    return markdown.rsplit("*Generated at", 1)[0]


@pytest.fixture
def agent(tmp_path, monkeypatch, make_daily):
    """An agent whose reports and papers both live under tmp_path."""
    instance = DailyReportAgent()
    instance.report_store = ReportStore(tmp_path / "reports")

    papers_dir = tmp_path / "papers"
    monkeypatch.setattr(instance.settings, "papers_base_dir", papers_dir)
    SkimStore(tmp_path, papers_dir=papers_dir).save(
        make_daily("2026-01-01", ["2601.00001"], [])
    )
    return instance


# --- render-level regression ----------------------------------------------


def test_omitting_trend_md_matches_the_pre_trend_output(agent):
    """The new parameter defaults to the exact output shape that existed before."""
    explicit = agent._generate_markdown("2026-01-01", [], [], None)
    default = agent._generate_markdown("2026-01-01", [], [])

    assert body(explicit) == body(default)
    assert TREND_MARKER not in default


def test_trend_section_lands_between_header_and_papers(agent):
    markdown = agent._generate_markdown("2026-01-01", [], [], SECTION)

    lines = markdown.splitlines()
    assert lines[0] == "# 2026-01-01 Daily Paper Report"
    assert lines[2].startswith("> 이 리포트는")

    trend_at = markdown.index(TREND_MARKER)
    papers_at = markdown.index("## 📚 오늘의 논문")
    header_at = markdown.index("# 2026-01-01 Daily Paper Report")
    assert header_at < trend_at < papers_at


def test_empty_trend_md_renders_no_section(agent):
    """A falsy section is the same as no section at all."""
    assert body(agent._generate_markdown("2026-01-01", [], [], "")) == body(
        agent._generate_markdown("2026-01-01", [], [], None)
    )


# --- toggle ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_toggle_off_produces_the_untouched_report(agent, monkeypatch, make_summary):
    monkeypatch.setattr(agent.settings, "trend_section_enabled", False)

    result = await agent.run(DailyReportInput("2026-01-01", [], []))
    markdown = (agent.report_store.get_report_path("2026-01-01")).read_text(encoding="utf-8")

    # 저장된 그날 스킴에 qualified 논문이 하나 있으므로 기타 표에 실린다.
    expected = agent._generate_markdown(
        "2026-01-01", [], [make_summary("2601.00001")], None
    )

    assert TREND_MARKER not in markdown
    assert body(markdown) == body(expected)
    assert result.total_papers == 0


@pytest.mark.asyncio
async def test_toggle_off_never_touches_the_papers_directory(agent, monkeypatch, tmp_path):
    """SkimStore is built inside the enabled branch, so no directory appears."""
    unused = tmp_path / "never-created"
    monkeypatch.setattr(agent.settings, "papers_base_dir", unused)
    monkeypatch.setattr(agent.settings, "trend_section_enabled", False)

    await agent.run(DailyReportInput("2026-01-01", [], []))

    assert not unused.exists()


@pytest.mark.asyncio
async def test_toggle_on_inserts_the_section(agent, monkeypatch):
    monkeypatch.setattr(agent.settings, "trend_section_enabled", True)

    await agent.run(DailyReportInput("2026-01-01", [], []))
    markdown = (agent.report_store.get_report_path("2026-01-01")).read_text(encoding="utf-8")

    assert TREND_MARKER in markdown
    assert markdown.index(TREND_MARKER) < markdown.index("## 📚 오늘의 논문")


@pytest.mark.asyncio
async def test_toggle_on_with_no_stored_skim_data_is_silent(agent, monkeypatch, tmp_path):
    """An empty window yields no section rather than an empty placeholder."""
    monkeypatch.setattr(agent.settings, "papers_base_dir", tmp_path / "empty-papers")
    monkeypatch.setattr(agent.settings, "trend_section_enabled", True)

    await agent.run(DailyReportInput("2026-01-01", [], []))
    markdown = (agent.report_store.get_report_path("2026-01-01")).read_text(encoding="utf-8")

    assert TREND_MARKER not in markdown


# --- window selection ------------------------------------------------------


def test_window_uses_existing_files_newest_first(agent, make_daily):
    store = SkimStore(agent.settings.base_dir, papers_dir=agent.settings.papers_dir)
    for date in ("2026-01-02", "2026-01-03", "2026-01-04"):
        store.save(make_daily(date, ["x" + date], []))

    window, previous = agent._load_trend_window()

    assert [out.date for out in window][:2] == ["2026-01-04", "2026-01-03"]
    assert previous == []


def test_window_splits_into_current_and_previous(agent, monkeypatch, make_daily):
    monkeypatch.setattr(agent.settings, "trend_window_days", 2)
    store = SkimStore(agent.settings.base_dir, papers_dir=agent.settings.papers_dir)
    for date in ("2026-01-02", "2026-01-03", "2026-01-04"):
        store.save(make_daily(date, ["x" + date], []))

    window, previous = agent._load_trend_window()

    assert [out.date for out in window] == ["2026-01-04", "2026-01-03"]
    assert [out.date for out in previous] == ["2026-01-02", "2026-01-01"]


def test_window_ignores_files_that_are_not_dates(agent, make_daily):
    (agent.settings.papers_dir / "notes.yaml").write_text("date: x\n", encoding="utf-8")

    window, _ = agent._load_trend_window()

    assert [out.date for out in window] == ["2026-01-01"]


def test_is_iso_date_rejects_non_dates():
    assert _is_iso_date("2026-01-01") is True
    assert _is_iso_date("notes") is False
    assert _is_iso_date("2026-13-01") is False
    assert _is_iso_date("2026-1-1") is False


def test_vocabulary_prefers_snapshot_then_configured_keywords(agent, make_daily):
    legacy = make_daily("2026-01-01", ["1"], [])
    assert agent._resolve_trend_vocab([legacy]) == agent.settings.get_effective_hf_keywords()

    snapshotted = make_daily("2026-01-02", ["2"], [], effective_keywords=["only-this"])
    assert agent._resolve_trend_vocab([snapshotted]) == ["only-this"]
