"""Markdown parser and Slack Block Kit converter.

Block budget: Slack caps a message at 50 blocks and a section at 3000
characters. A paper is rendered as one combined section rather than one block
per field, because the per-paper text averages ~780 characters - a fraction of
the section limit - while one block per field burned the block budget at five
papers and silently dropped the whole message.
"""

import re
from typing import Any

from .models import BenchmarkEntry, PaperSummary, SkimPaper

SECTION_TEXT_LIMIT = 3000
_SECTION_TEXT_MARGIN = 100
MAX_SKIM_KEYWORDS = 3
SKIM_ONE_LINER_LIMIT = 60


def parse_report(
    content: str,
) -> tuple[list[PaperSummary], list[SkimPaper]]:
    """Parse markdown report content into paper summaries.

    Args:
        content: Raw markdown content of the report.

    Returns:
        Tuple of (deep analysis papers, skim-only papers).
    """
    papers = []

    # "기타 주목할 논문" 섹션 이전 부분만 딥 분석 파싱에 사용
    skim_marker = "## 📋 기타 주목할 논문"
    deep_section = content.split(skim_marker)[0] if skim_marker in content else content

    # Split by paper sections (### N. Title pattern)
    paper_pattern = r"### \d+\.\s+"
    sections = re.split(paper_pattern, deep_section)

    # Skip the first section (header)
    for section in sections[1:]:
        if not section.strip():
            continue

        paper = _parse_paper_section(section)
        if paper:
            papers.append(paper)

    # 스킴 요약 테이블 파싱
    skim_papers = _parse_skim_summary_section(content)

    return papers, skim_papers


def _parse_paper_section(section: str) -> PaperSummary | None:
    """Parse a single paper section.

    Args:
        section: Markdown content for one paper.

    Returns:
        PaperSummary if parsing succeeds, None otherwise.
    """
    # Extract title, stars, and GitHub badge
    # Pattern: Title ⭐⭐⭐⭐ [GitHub ✓] or Title ⭐⭐⭐⭐
    title_match = re.match(r"^(.+?)\s*(⭐+)\s*(?:\[GitHub ✓\])?\s*$", section.split("\n")[0])
    if not title_match:
        return None

    title = title_match.group(1).strip()
    stars = len(title_match.group(2))
    has_github_badge = "[GitHub ✓]" in section.split("\n")[0]

    # Extract arXiv ID and URL
    arxiv_match = re.search(r"\*\*arXiv\*\*:\s*\[(\d+\.\d+)\]\((https://arxiv\.org/abs/\d+\.\d+)\)", section)
    if not arxiv_match:
        return None

    arxiv_id = arxiv_match.group(1)
    arxiv_url = arxiv_match.group(2)

    # Extract GitHub URL if present
    github_match = re.search(r"\*\*GitHub\*\*:\s*\[(https://github\.com/[^\]]+)\]|"
                             r"\*\*GitHub\*\*:\s*(https://github\.com/\S+)", section)
    github_url = None
    if github_match:
        github_url = github_match.group(1) or github_match.group(2)

    # Extract score
    score_match = re.search(r"총점:\s*(\d+)/(\d+)", section)
    if not score_match:
        return None

    score = int(score_match.group(1))
    max_score = int(score_match.group(2))

    # Extract summary (한 줄 요약)
    summary_match = re.search(r"## 한 줄 요약\s*\n(.+?)(?=\n##|\n---|\Z)", section, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else ""

    # Extract problem definition (문제 정의 - 기존 방법의 한계)
    problem_match = re.search(r"\*\*기존 방법의 한계\*\*:\s*(.+?)(?=\n##|\n\*\*|\n---|\Z)", section, re.DOTALL)
    problem = problem_match.group(1).strip() if problem_match else ""

    # Extract matched keywords (매칭 키워드)
    keywords_match = re.search(r"\*\*매칭 키워드\*\*:\s*(.+?)(?=\n|\Z)", section)
    matched_keywords = [kw.strip() for kw in keywords_match.group(1).split(",")] if keywords_match else []

    # Extract core contributions (핵심 기여)
    contributions_match = re.search(r"## 핵심 기여\s*\n(.+?)(?=\n##|\n---|\Z)", section, re.DOTALL)
    contributions = contributions_match.group(1).strip() if contributions_match else ""

    # Extract methodology (방법론)
    methodology_match = re.search(r"## 방법론\s*\n(.+?)(?=\n##|\n---|\Z)", section, re.DOTALL)
    methodology = methodology_match.group(1).strip() if methodology_match else ""

    # Extract when to use
    when_to_use_match = re.search(r"✅\s*\*\*사용 권장\*\*:\s*(.+?)(?=\n❌|\n##|\n---|\Z)", section, re.DOTALL)
    when_to_use = when_to_use_match.group(1).strip() if when_to_use_match else ""

    # Extract when not to use
    when_not_to_use_match = re.search(r"❌\s*\*\*사용 비권장\*\*:\s*(.+?)(?=\n##|\n---|\Z)", section, re.DOTALL)
    when_not_to_use = when_not_to_use_match.group(1).strip() if when_not_to_use_match else ""

    return PaperSummary(
        title=title,
        arxiv_id=arxiv_id,
        arxiv_url=arxiv_url,
        score=score,
        max_score=max_score,
        stars=stars,
        summary=summary,
        problem=problem,
        contributions=contributions,
        methodology=methodology,
        when_to_use=when_to_use,
        when_not_to_use=when_not_to_use,
        matched_keywords=matched_keywords,
        github_url=github_url,
    )


def _parse_skim_summary_section(content: str) -> list[SkimPaper]:
    """스킴 요약 테이블을 파싱하여 SkimPaper 리스트로 반환."""
    skim_marker = "## 📋 기타 주목할 논문"
    if skim_marker not in content:
        return []

    skim_section = content.split(skim_marker, 1)[1]

    papers: list[SkimPaper] = []
    # 테이블 행 파싱: | N | [Title](url) | `kw1`, `kw2` | category | one_liner |
    row_pattern = re.compile(
        r"\|\s*\d+\s*\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(.*?)\s*\|\s*(\S+)\s*\|\s*(.*?)\s*\|"
    )
    for match in row_pattern.finditer(skim_section):
        title = match.group(1)
        arxiv_url = match.group(2)
        raw_keywords = match.group(3).strip()
        category = match.group(4).strip()
        one_liner = match.group(5).strip()

        # `kw1`, `kw2` → ["kw1", "kw2"]
        keywords = [kw.strip().strip("`") for kw in raw_keywords.split(",") if kw.strip()]

        papers.append(SkimPaper(
            title=title,
            arxiv_url=arxiv_url,
            matched_keywords=keywords,
            category=category,
            one_liner=one_liner,
        ))

    return papers


def _format_benchmark(entry: BenchmarkEntry) -> str:
    """Render one benchmark row.

    Result dict keys carry two different meanings across the corpus: metric
    names for ~24% of entries and system names for the rest. When both sides
    share keys they are metric names, so baseline and proposed can be shown as a
    direct before/after; otherwise the two sides are listed separately because
    pairing them would invent a comparison the data does not make.
    """
    shared = entry.shared_metric_keys
    if shared:
        body = " · ".join(
            f"{key} {entry.baseline_results[key]}→{entry.proposed_results[key]}"
            for key in shared[:3]
        )
    else:
        baseline = " / ".join(f"{k} {v}" for k, v in list(entry.baseline_results.items())[:2])
        proposed = ", ".join(f"{k} {v}" for k, v in list(entry.proposed_results.items())[:2])
        body = f"{baseline} → *{proposed}*" if baseline else f"*{proposed}*"
    return f"• *{entry.dataset}*: {body}"


def _paper_body_text(paper: PaperSummary) -> str:
    """Build the combined body section shared by both block variants.

    Sections with no data are skipped entirely, matching how every other
    renderer in this project treats empty values.
    """
    parts: list[str] = []

    meta = [f"⭐ {paper.score}/{paper.max_score}"]
    if paper.matched_keywords:
        meta.append("🏷️ " + " · ".join(f"`{kw}`" for kw in paper.matched_keywords))
    parts.append("  ·  ".join(meta))

    if paper.headline:
        parts.append(f"📝 {paper.headline}")

    if paper.problem:
        parts.append(f"🔍 *문제:* {paper.problem}")

    if paper.delta_axes:
        lines = ["🔀 *델타*"]
        for axis in paper.delta_axes:
            lines.append(f"• *{axis.axis}*: {axis.old_approach} → {axis.new_approach}")
            if axis.hint:
                lines.append(f"   _구현: {axis.hint}_")
        parts.append("\n".join(lines))

    if paper.benchmarks:
        header = "📊 *벤치마크*"
        if paper.benchmark_total > len(paper.benchmarks):
            header += f" ({paper.benchmark_total}개 중 {len(paper.benchmarks)}개)"
        parts.append("\n".join([header] + [_format_benchmark(b) for b in paper.benchmarks]))

    recommendations = []
    if paper.when_to_use:
        recommendations.append(f"✅ *권장:* {paper.when_to_use}")
    if paper.when_not_to_use:
        recommendations.append(f"❌ *비권장:* {paper.when_not_to_use}")
    if recommendations:
        parts.append("\n".join(recommendations))

    footer = []
    if paper.verification:
        verification = f"🔎 검증 {paper.verification.verified_count}/{paper.verification.total_claims}"
        if paper.verification.unverified_count:
            verification += f" (미검증 {paper.verification.unverified_count})"
        if paper.verification.contradicted_count:
            verification += f" ⚠️ 모순 {paper.verification.contradicted_count}"
        footer.append(verification)
    if paper.github_url:
        footer.append(f"💻 <{paper.github_url}|GitHub>")
    if footer:
        parts.append("  ·  ".join(footer))

    return _truncate_section("\n".join(parts))


def _truncate_section(text: str) -> str:
    """Keep a section under Slack's 3000 character cap."""
    if len(text) <= SECTION_TEXT_LIMIT:
        return text
    return text[:SECTION_TEXT_LIMIT - 1].rstrip() + "…"


def _paper_title_block(paper: PaperSummary, index: int) -> dict[str, Any]:
    github_badge = " :github:" if paper.has_github else ""
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{index}. {paper.title}*  {paper.star_emoji}{github_badge}"
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "arXiv",
                "emoji": True
            },
            "url": paper.arxiv_url,
            "action_id": f"arxiv-{paper.arxiv_id}"
        }
    }


def _vote_actions_block(
    paper: PaperSummary,
    index: int,
    report_date: str,
    applicable_count: int,
    idea_count: int,
    pass_count: int,
) -> dict[str, Any]:
    """Voting buttons. The action_id and value format are a wire contract with
    the interaction handler in server.py and must not change."""
    action_value = f"{report_date}|{paper.arxiv_id}|{paper.title}"
    return {
        "type": "actions",
        "block_id": f"vote-{index}-{paper.arxiv_id}",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": f"🔧 실무 적용 ({applicable_count})",
                    "emoji": True
                },
                "style": "primary",
                "action_id": "vote_applicable",
                "value": action_value,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": f"💡 아이디어 ({idea_count})",
                    "emoji": True
                },
                "action_id": "vote_idea",
                "value": action_value,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": f"⏭️ 패스 ({pass_count})",
                    "emoji": True
                },
                "action_id": "vote_pass",
                "value": action_value,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "💬 댓글",
                    "emoji": True
                },
                "action_id": "add_comment",
                "value": action_value,
            },
        ]
    }


def _paper_to_blocks(paper: PaperSummary, index: int) -> list[dict[str, Any]]:
    """Convert a single paper to Slack blocks (3 blocks, no voting).

    Args:
        paper: Paper summary.
        index: Paper index (1-based).

    Returns:
        List of Slack blocks for this paper.
    """
    return [
        _paper_title_block(paper, index),
        {"type": "section", "text": {"type": "mrkdwn", "text": _paper_body_text(paper)}},
        {"type": "divider"},
    ]


def _paper_to_blocks_interactive(
    paper: PaperSummary,
    index: int,
    report_date: str,
    applicable_count: int = 0,
    idea_count: int = 0,
    pass_count: int = 0,
) -> list[dict[str, Any]]:
    """Convert a single paper to Slack blocks with voting buttons (4 blocks).

    Args:
        paper: Paper summary.
        index: Paper index (1-based).
        report_date: Report date for action value.
        applicable_count: Current applicable vote count.
        idea_count: Current idea vote count.
        pass_count: Current pass vote count.

    Returns:
        List of Slack blocks for this paper.
    """
    return [
        _paper_title_block(paper, index),
        {"type": "section", "text": {"type": "mrkdwn", "text": _paper_body_text(paper)}},
        _vote_actions_block(paper, index, report_date, applicable_count, idea_count, pass_count),
        {"type": "divider"},
    ]


def _skim_papers_to_blocks(skim_papers: list[SkimPaper]) -> list[dict[str, Any]]:
    """스킴 요약 논문을 단일 Slack 블록으로 렌더링.

    한 편에 두 블록(section + context)을 쓰면 스킴 11편만으로 24블록이 나가
    딥 논문이 들어갈 자리가 사라진다. 목록 전체를 한 section에 담는다.
    """
    lines = [f"*📋 기타 주목할 논문 ({len(skim_papers)}편)*"]
    for paper in skim_papers:
        entry = f"• <{paper.arxiv_url}|{paper.title}>"
        if paper.one_liner:
            entry += f" — {_clip_one_liner(paper.one_liner)}"
        if paper.matched_keywords:
            entry += "  " + " ".join(f"`{kw}`" for kw in paper.matched_keywords[:MAX_SKIM_KEYWORDS])
        lines.append(entry)

    # 한도를 넘으면 뒤에서부터 접고 몇 편이 잘렸는지 남긴다 - 조용히 자르면
    # 독자가 목록이 전부라고 오해한다.
    shown = len(lines) - 1
    text = "\n".join(lines)
    while shown > 0 and len(text) > SECTION_TEXT_LIMIT - _SECTION_TEXT_MARGIN:
        shown -= 1
        text = "\n".join(lines[:shown + 1] + [f"… 외 {len(skim_papers) - shown}편"])

    return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]


def _clip_one_liner(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= SKIM_ONE_LINER_LIMIT:
        return collapsed
    return collapsed[:SKIM_ONE_LINER_LIMIT].rstrip() + "…"


def _overview_blocks(papers: list[PaperSummary], date: str, note: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📚 Paper Digest - {date}",
                "emoji": True
            }
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"오늘의 논문 *{len(papers)}*편{note}"
            }]
        },
        {"type": "divider"},
    ]


def to_slack_blocks(
    papers: list[PaperSummary],
    date: str,
    skim_papers: list[SkimPaper] | None = None,
) -> list[dict[str, Any]]:
    """Convert paper summaries to Slack Block Kit format.

    Args:
        papers: List of parsed paper summaries.
        date: Report date string.
        skim_papers: Optional list of skim-only papers.

    Returns:
        Slack Block Kit blocks list.
    """
    blocks = _overview_blocks(papers, date, "")

    for i, paper in enumerate(papers):
        blocks.extend(_paper_to_blocks(paper, i + 1))

    if skim_papers:
        blocks.extend(_skim_papers_to_blocks(skim_papers))

    return blocks


def to_slack_payload(
    papers: list[PaperSummary],
    date: str,
    skim_papers: list[SkimPaper] | None = None,
) -> dict[str, Any]:
    """Create complete Slack webhook payload.

    Args:
        papers: List of parsed paper summaries.
        date: Report date string.
        skim_papers: Optional list of skim-only papers.

    Returns:
        Complete Slack webhook payload.
    """
    return {
        "blocks": to_slack_blocks(papers, date, skim_papers),
        "text": f"📚 Paper Digest - {date}: {len(papers)}편의 논문"
    }


def to_slack_blocks_interactive(
    papers: list[PaperSummary],
    date: str,
    vote_counts: dict[str, dict[str, int]] | None = None,
    skim_papers: list[SkimPaper] | None = None,
) -> list[dict[str, Any]]:
    """Convert paper summaries to Slack Block Kit format with voting buttons.

    Args:
        papers: List of parsed paper summaries.
        date: Report date string.
        vote_counts: Optional dict of arxiv_id -> {"applicable_count": N, "idea_count": M, "pass_count": K}
        skim_papers: Optional list of skim-only papers.

    Returns:
        Slack Block Kit blocks list with interactive voting.
    """
    vote_counts = vote_counts or {}
    blocks = _overview_blocks(
        papers, date, " | 🔧 실무 적용 · 💡 아이디어 · ⏭️ 패스 로 투표하세요!"
    )

    for i, paper in enumerate(papers):
        counts = vote_counts.get(paper.arxiv_id, {"applicable_count": 0, "idea_count": 0, "pass_count": 0})
        blocks.extend(_paper_to_blocks_interactive(
            paper,
            i + 1,
            date,
            counts.get("applicable_count", 0),
            counts.get("idea_count", 0),
            counts.get("pass_count", 0),
        ))

    if skim_papers:
        blocks.extend(_skim_papers_to_blocks(skim_papers))

    return blocks


def to_slack_payload_interactive(
    papers: list[PaperSummary],
    date: str,
    vote_counts: dict[str, dict[str, int]] | None = None,
    skim_papers: list[SkimPaper] | None = None,
) -> dict[str, Any]:
    """Create Slack webhook payload with voting buttons.

    Args:
        papers: List of parsed paper summaries.
        date: Report date string.
        vote_counts: Optional dict of arxiv_id -> {"applicable_count": N, "idea_count": M, "pass_count": K}
        skim_papers: Optional list of skim-only papers.

    Returns:
        Complete Slack webhook payload with interactive voting.
    """
    return {
        "blocks": to_slack_blocks_interactive(papers, date, vote_counts, skim_papers),
        "text": f"📚 Paper Digest - {date}: {len(papers)}편의 논문"
    }
