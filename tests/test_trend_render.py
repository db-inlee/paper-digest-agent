"""The rendered section must stay out of the report parser's way."""

import re

from rtc.schemas.trend import CountDelta, TrendRepresentative, TrendSummary
from rtc.trend import render_trend_section

PAPER_HEADING = re.compile(r"^### \d+\.", re.MULTILINE)


def summary(**kwargs) -> TrendSummary:
    base = dict(
        window_dates=["2026-01-01", "2026-01-02"],
        window_papers=10,
        keyword_dates=["2026-01-01"],
        keyword_papers=6,
        keywords=[CountDelta(name="agent", count=5)],
        categories=[CountDelta(name="agent", count=7)],
        top_tags=[CountDelta(name="reinforcement learning", count=4)],
        outside_signals=[CountDelta(name="reinforcement learning", count=4)],
    )
    base.update(kwargs)
    return TrendSummary(**base)


def test_empty_summary_renders_nothing():
    assert render_trend_section(TrendSummary()) == ""


def test_section_reports_window_shape_and_axes():
    text = render_trend_section(summary())

    assert text.startswith("## 📈 트렌드 브리핑 (창 2일 · 10편)")
    assert "**키워드** (1일 6편): agent 5" in text
    assert "**카테고리**: agent 7" in text
    assert "**필터 밖 신호**: reinforcement learning 4" in text


def test_section_avoids_report_parser_markers():
    """`##` heading, and none of the markers parse_report keys on."""
    text = render_trend_section(
        summary(
            vocabulary_changed=True,
            new_keywords=[CountDelta(name="RAG", count=3)],
            new_tags=[CountDelta(name="rl", count=3)],
            representatives=[
                TrendRepresentative(
                    signal="agent",
                    signal_kind="keyword",
                    arxiv_id="2601.00001",
                    title="A Paper",
                    one_liner="설명",
                    link="https://arxiv.org/abs/2601.00001",
                )
            ],
        )
    )

    assert "⭐" not in text
    assert "**arXiv**:" not in text
    assert "총점:" not in text
    assert PAPER_HEADING.search(text) is None
    for line in text.splitlines():
        assert not line.startswith("### ")


def test_forbidden_markers_are_stripped_from_paper_text():
    """A hostile title cannot smuggle parser markers into the section."""
    text = render_trend_section(
        summary(
            representatives=[
                TrendRepresentative(
                    signal="agent",
                    signal_kind="keyword",
                    arxiv_id="2601.00001",
                    title="Bad ⭐⭐⭐⭐ Title **arXiv**: x",
                    one_liner="총점: 15/15\n두 번째 줄",
                    link="https://arxiv.org/abs/2601.00001",
                )
            ]
        )
    )

    assert "⭐" not in text
    assert "**arXiv**:" not in text
    assert "총점:" not in text
    assert "두 번째 줄" in text


def test_deltas_render_as_arrows_and_zero_is_silent():
    text = render_trend_section(
        summary(
            has_previous=True,
            keywords=[
                CountDelta(name="up", count=5, previous=1),
                CountDelta(name="down", count=1, previous=5),
                CountDelta(name="flat", count=2, previous=2),
            ],
        )
    )

    assert "up 5 (↑4)" in text
    assert "down 1 (↓4)" in text
    assert "flat 2" in text and "flat 2 (" not in text


def test_vocabulary_change_is_flagged():
    assert "어휘가 변경" in render_trend_section(summary(vocabulary_changed=True))
    assert "어휘가 변경" not in render_trend_section(summary())


def test_axes_without_data_are_skipped_entirely():
    text = render_trend_section(
        summary(top_tags=[], outside_signals=[], new_keywords=[], new_tags=[])
    )

    assert "태그 상위" not in text
    assert "필터 밖 신호" not in text
    assert "신규" not in text
