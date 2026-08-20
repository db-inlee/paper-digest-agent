"""Render a TrendSummary as a markdown section.

The section is consumed by notifier's ``parse_report``, which splits papers on
``### \\d+\\.`` and reads star ratings / ``**arXiv**:`` / ``총점:`` markers. Using
``##`` headings and keeping those markers out of the section is what stops the
briefing from being mis-parsed as an extra paper.
"""

from rtc.schemas.trend import CountDelta, TrendSummary

SECTION_HEADING = "## 📈 트렌드 브리핑"

# Patterns that would make notifier's report parser treat this text as a paper.
FORBIDDEN_PATTERNS = ("⭐", "**arXiv**:", "총점:")

ONE_LINER_MAX = 90


def render_trend_section(summary: TrendSummary) -> str:
    """Render the briefing, or an empty string when there is nothing to show.

    Args:
        summary: 집계 결과

    Returns:
        마크다운 섹션 문자열 (빈 집계면 "")
    """
    if summary.is_empty:
        return ""

    lines = [_heading(summary), ""]

    if summary.vocabulary_changed:
        lines.append("> ⚠️ 창 기간 중 키워드 어휘가 변경되었습니다 — 빈도 비교에 주의하세요.")
        lines.append("")

    body: list[str] = []
    if summary.keywords:
        scope = f"{len(summary.keyword_dates)}일 {summary.keyword_papers}편"
        body.append(f"**키워드** ({scope}): {_join_counts(summary.keywords)}")
    if summary.categories:
        body.append(f"**카테고리**: {_join_counts(summary.categories, sep=' → ')}")
    if summary.top_tags:
        body.append(f"**태그 상위**: {_join_counts(summary.top_tags)}")
    if summary.outside_signals:
        body.append(f"**필터 밖 신호**: {_join_counts(summary.outside_signals)}")
    if summary.new_keywords:
        body.append(f"**신규 키워드**: {_join_counts(summary.new_keywords)}")
    if summary.new_tags:
        body.append(f"**신규 태그**: {_join_counts(summary.new_tags)}")

    lines.extend(body)

    for rep in summary.representatives:
        lines.append("")
        title = _sanitize(rep.title)
        one_liner = _truncate(_sanitize(rep.one_liner), ONE_LINER_MAX)
        lines.append(f"**대표** · `{_sanitize(rep.signal)}`: [{title}]({rep.link})")
        if one_liner:
            lines.append(f"  {one_liner}")

    lines.append("")
    return "\n".join(lines)


def _heading(summary: TrendSummary) -> str:
    """Window shape first - every number below is scoped by it."""
    return (
        f"{SECTION_HEADING} (창 {len(summary.window_dates)}일 · {summary.window_papers}편)"
    )


def _join_counts(counts: list[CountDelta], sep: str = " · ") -> str:
    return sep.join(_format_count(c) for c in counts)


def _format_count(count: CountDelta) -> str:
    """``name N`` plus an arrow when a previous window made a delta meaningful."""
    text = f"{_sanitize(count.name)} {count.count}"
    delta = count.delta
    if delta:
        arrow = "↑" if delta > 0 else "↓"
        text += f" ({arrow}{abs(delta)})"
    return text


def _sanitize(text: str) -> str:
    """Strip markers that would confuse the report parser, and flatten newlines."""
    cleaned = " ".join(text.split())
    for pattern in FORBIDDEN_PATTERNS:
        cleaned = cleaned.replace(pattern, "")
    return cleaned.strip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
