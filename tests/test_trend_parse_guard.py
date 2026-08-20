"""The trend section must be invisible to notifier's report parser.

parse_report splits papers on ``### \\d+\\.`` and reads star ratings,
``**arXiv**:`` and ``총점:``. A ``##`` section that avoids those markers has to
leave the parsed result byte-for-byte unchanged.
"""

import pytest
from rtc.schemas.trend import CountDelta, TrendRepresentative, TrendSummary
from rtc.trend import render_trend_section

parse_report = pytest.importorskip("toslack.converter").parse_report

REPORT = """# 2026-01-01 Daily Paper Report

> 이 리포트는 논문을 상세히 분석하기 위한 것이 아니라,
> 최근 연구 흐름을 빠르게 파악하기 위한 데일리 요약입니다.

## 📚 오늘의 논문 (1편)

---

### 1. Sample Paper ⭐⭐⭐⭐

**arXiv**: [2601.00001](https://arxiv.org/abs/2601.00001)
**매칭 키워드**: agent

## 왜 이 논문인가?
총점: 11/15

## 한 줄 요약
샘플 요약

---

## 📋 기타 주목할 논문

| # | 논문 | 키워드 | 카테고리 | 한줄 요약 |
|---|------|--------|----------|-----------|
| 1 | [Skim Paper](https://arxiv.org/abs/2601.00002) | `agent` | agent | 스킴 요약 |

---

*Generated at 2026-01-01 09:00:00*
"""

TREND_SUMMARY = TrendSummary(
    window_dates=["2026-01-01", "2026-01-02"],
    window_papers=86,
    keyword_dates=["2026-01-01"],
    keyword_papers=63,
    keywords=[
        CountDelta(name="reasoning", count=34, previous=20),
        CountDelta(name="LLM", count=33),
    ],
    categories=[CountDelta(name="agent", count=31)],
    top_tags=[CountDelta(name="reinforcement learning", count=26)],
    outside_signals=[CountDelta(name="reinforcement learning", count=26)],
    new_tags=[CountDelta(name="benchmark", count=10)],
    vocabulary_changed=True,
    representatives=[
        TrendRepresentative(
            signal="reasoning",
            signal_kind="keyword",
            arxiv_id="2601.00009",
            title="Representative Paper",
            one_liner="대표 논문 한 줄 요약",
            link="https://arxiv.org/abs/2601.00009",
        )
    ],
)


def insert_section(report: str, section: str) -> str:
    marker = "## 📚 오늘의 논문"
    head, rest = report.split(marker, 1)
    return head + section + marker + rest


def parsed(report: str):
    papers, skim = parse_report(report)
    return (
        [(p.arxiv_id, p.title, p.score, p.stars) for p in papers],
        [(s.title, s.arxiv_url) for s in skim],
    )


def test_trend_section_does_not_change_the_parsed_report():
    section = render_trend_section(TREND_SUMMARY)
    assert section

    assert parsed(insert_section(REPORT, section)) == parsed(REPORT)


def test_baseline_report_parses_as_expected():
    """Guards the guard: the fixture really does contain one paper of each kind."""
    papers, skim = parsed(REPORT)

    assert [p[0] for p in papers] == ["2601.00001"]
    assert [s[0] for s in skim] == ["Skim Paper"]


def test_a_section_carrying_paper_markers_would_be_mis_parsed():
    """Shows what the guarded markers actually cost - the guard is not cosmetic."""
    hostile = (
        "## 📈 트렌드 브리핑\n\n"
        "### 1. reasoning 34 ⭐⭐⭐⭐\n\n"
        "**arXiv**: [2601.99999](https://arxiv.org/abs/2601.99999)\n"
        "총점: 11/15\n\n"
    )

    papers, _ = parsed(insert_section(REPORT, hostile))

    assert [p[0] for p in papers] == ["2601.99999", "2601.00001"]
