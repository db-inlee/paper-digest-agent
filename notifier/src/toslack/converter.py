"""Markdown parser and Slack Block Kit converter."""

import re
from typing import Any

from .models import PaperSummary, SkimPaper


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
    blocks: list[dict[str, Any]] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"📚 Paper Digest - {date}",
            "emoji": True
        }
    })

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"오늘의 논문 *{len(papers)}*편"
        }]
    })

    blocks.append({"type": "divider"})

    # Each paper
    for i, paper in enumerate(papers):
        blocks.extend(_paper_to_blocks(paper, i + 1))

    # 스킴 요약 섹션
    if skim_papers:
        blocks.extend(_skim_papers_to_blocks(skim_papers))

    return blocks


def _paper_to_blocks(paper: PaperSummary, index: int) -> list[dict[str, Any]]:
    """Convert a single paper to Slack blocks.

    Args:
        paper: Paper summary.
        index: Paper index (1-based).

    Returns:
        List of Slack blocks for this paper.
    """
    blocks: list[dict[str, Any]] = []

    # Title with stars and GitHub badge
    github_badge = " :github:" if paper.has_github else ""
    title_text = f"*{index}. {paper.title}*  {paper.star_emoji}{github_badge}"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": title_text
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
    })

    # Score and matched keywords
    score_fields = [
        {
            "type": "mrkdwn",
            "text": f"*총점:* {paper.score}/{paper.max_score}"
        },
        {
            "type": "mrkdwn",
            "text": f"*arXiv:* {paper.arxiv_id}"
        }
    ]
    blocks.append({
        "type": "section",
        "fields": score_fields
    })

    if paper.matched_keywords:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"🏷️ 매칭 키워드: {' · '.join(f'`{kw}`' for kw in paper.matched_keywords)}"
            }]
        })

    # Summary
    if paper.summary:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📝 {paper.summary}"
            }
        })

    # Problem definition
    if paper.problem:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔍 *문제 정의:* {paper.problem}"
            }
        })

    # Core contributions
    if paper.contributions:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🎯 *핵심 기여:*\n{paper.contributions}"
            }
        })

    # Methodology
    if paper.methodology:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚙️ *방법론:*\n{paper.methodology}"
            }
        })

    # When to use / not to use
    recommendations = []
    if paper.when_to_use:
        recommendations.append(f"✅ *사용 권장:* {paper.when_to_use}")
    if paper.when_not_to_use:
        recommendations.append(f"❌ *사용 비권장:* {paper.when_not_to_use}")

    if recommendations:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(recommendations)
            }
        })

    # GitHub link if available
    if paper.github_url:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"💻 <{paper.github_url}|GitHub Repository>"
            }]
        })

    blocks.append({"type": "divider"})

    return blocks


def _paper_to_blocks_interactive(
    paper: PaperSummary,
    index: int,
    report_date: str,
    applicable_count: int = 0,
    idea_count: int = 0,
    pass_count: int = 0,
) -> list[dict[str, Any]]:
    """Convert a single paper to Slack blocks with voting buttons.

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
    blocks: list[dict[str, Any]] = []

    # Title with stars and GitHub badge
    github_badge = " :github:" if paper.has_github else ""
    title_text = f"*{index}. {paper.title}*  {paper.star_emoji}{github_badge}"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": title_text
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
    })

    # Score and matched keywords
    blocks.append({
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": f"*총점:* {paper.score}/{paper.max_score}"
            },
            {
                "type": "mrkdwn",
                "text": f"*arXiv:* {paper.arxiv_id}"
            }
        ]
    })

    if paper.matched_keywords:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"🏷️ 매칭 키워드: {' · '.join(f'`{kw}`' for kw in paper.matched_keywords)}"
            }]
        })

    # Summary
    if paper.summary:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📝 {paper.summary}"
            }
        })

    # Problem definition
    if paper.problem:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔍 *문제 정의:* {paper.problem}"
            }
        })

    # Core contributions
    if paper.contributions:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🎯 *핵심 기여:*\n{paper.contributions}"
            }
        })

    # Methodology
    if paper.methodology:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚙️ *방법론:*\n{paper.methodology}"
            }
        })

    # When to use / not to use
    recommendations = []
    if paper.when_to_use:
        recommendations.append(f"✅ *사용 권장:* {paper.when_to_use}")
    if paper.when_not_to_use:
        recommendations.append(f"❌ *사용 비권장:* {paper.when_not_to_use}")

    if recommendations:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(recommendations)
            }
        })

    # GitHub link if available
    if paper.github_url:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"💻 <{paper.github_url}|GitHub Repository>"
            }]
        })

    # Voting buttons with counts (3 buttons + comment)
    action_value = f"{report_date}|{paper.arxiv_id}|{paper.title}"
    blocks.append({
        "type": "actions",
        "block_id": f"vote-{paper.arxiv_id}",
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
    })

    blocks.append({"type": "divider"})

    return blocks


def _skim_papers_to_blocks(skim_papers: list[SkimPaper]) -> list[dict[str, Any]]:
    """스킴 요약 논문을 Slack context 블록으로 렌더링."""
    blocks: list[dict[str, Any]] = []

    blocks.append({"type": "divider"})

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"📋 *기타 주목할 논문* ({len(skim_papers)}편)"
        }
    })

    # Slack context 블록은 elements 최대 10개 제한 → 5개씩 분할
    batch_size = 5
    for start in range(0, len(skim_papers), batch_size):
        batch = skim_papers[start:start + batch_size]
        elements = []
        for paper in batch:
            kw_text = " · ".join(f"`{kw}`" for kw in paper.matched_keywords) if paper.matched_keywords else ""
            line = f"• <{paper.arxiv_url}|{paper.title}> — {paper.one_liner}"
            if kw_text:
                line += f" ({kw_text})"
            elements.append({"type": "mrkdwn", "text": line})

        blocks.append({
            "type": "context",
            "elements": elements,
        })

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
) -> list[dict[str, Any]]:
    """Convert paper summaries to Slack Block Kit format with voting buttons.

    Args:
        papers: List of parsed paper summaries.
        date: Report date string.
        vote_counts: Optional dict of arxiv_id -> {"applicable_count": N, "idea_count": M, "pass_count": K}

    Returns:
        Slack Block Kit blocks list with interactive voting.
    """
    blocks: list[dict[str, Any]] = []
    vote_counts = vote_counts or {}

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"📚 Paper Digest - {date}",
            "emoji": True
        }
    })

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"오늘의 논문 *{len(papers)}*편 | 🔧 실무 적용 · 💡 아이디어 · ⏭️ 패스 로 투표하세요!"
        }]
    })

    blocks.append({"type": "divider"})

    # Each paper with voting buttons
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

    return blocks


def to_slack_payload_interactive(
    papers: list[PaperSummary],
    date: str,
    vote_counts: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    """Create Slack webhook payload with voting buttons.

    Args:
        papers: List of parsed paper summaries.
        date: Report date string.
        vote_counts: Optional dict of arxiv_id -> {"keep_count": N, "drop_count": M}

    Returns:
        Complete Slack webhook payload with interactive voting.
    """
    return {
        "blocks": to_slack_blocks_interactive(papers, date, vote_counts),
        "text": f"📚 Paper Digest - {date}: {len(papers)}편의 논문"
    }
