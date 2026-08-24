"""Block budget and structure of the Slack renderer.

Slack drops a whole message over 50 blocks, silently. These tests pin the
per-paper block count so that budget can be reasoned about, and pin the voting
button payload, which is a wire contract with the interaction handler.
"""

import pytest

converter = pytest.importorskip("toslack.converter")
models = pytest.importorskip("toslack.models")
enrich = pytest.importorskip("toslack.enrich")

SLACK_BLOCK_LIMIT = 50
SECTION_TEXT_LIMIT = 3000


def paper(arxiv_id: str = "2608.19197", **overrides) -> models.PaperSummary:
    fields = dict(
        title="Some Paper",
        arxiv_id=arxiv_id,
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        score=12,
        max_score=15,
        stars=4,
        summary="markdown summary",
        problem="the limitation",
        contributions="- a contribution",
        methodology="### Component\ndescription",
        when_to_use="when it fits",
        when_not_to_use="when it does not",
        matched_keywords=["agent", "rl"],
        github_url="https://github.com/x/y",
    )
    fields.update(overrides)
    return models.PaperSummary(**fields)


def skim(arxiv_id: str) -> models.SkimPaper:
    return models.SkimPaper(
        title=f"Skim {arxiv_id}",
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        matched_keywords=["agent", "rl", "llm", "extra"],
        category="agent",
        one_liner="a short summary of the skimmed paper",
    )


DETAIL = {
    "delta": {
        "one_line_takeaway": "takeaway from delta.json",
        "core_deltas": [
            {"axis": "control", "old_approach": "fixed", "new_approach": "adaptive"},
            {"axis": "reward", "old_approach": "static", "new_approach": "regret based"},
        ],
    },
    "extraction": {
        "benchmarks": [{
            "dataset": "AIME",
            "metrics": ["Avg@32"],
            "baseline_results": {"GRPO": "61.2"},
            "proposed_results": {"SPADE": "62.8"},
        }],
        "method_components": [
            {"name": "control", "description": "adaptive control",
             "implementation_hint": "run adaptively"},
            {"name": "reward", "description": "regret based reward",
             "implementation_hint": "compute regret"},
        ],
    },
    "verification": {
        "total_claims": 5, "verified_count": 4,
        "unverified_count": 1, "contradicted_count": 0,
    },
}


def enriched(count: int) -> list[models.PaperSummary]:
    papers = [paper(f"2608.1000{i}") for i in range(count)]
    return enrich.enrich_papers(papers, loader=lambda _: DETAIL)


# --- per-paper block count ------------------------------------------------


def test_slack_blocks_per_paper_is_four():
    """The interactive variant renders title, body, actions, divider - nothing more."""
    blocks = converter._paper_to_blocks_interactive(enriched(1)[0], 1, "2026-08-21")

    assert len(blocks) == 4
    assert [b["type"] for b in blocks] == ["section", "section", "actions", "divider"]


def test_non_interactive_blocks_per_paper_is_three():
    """The non-interactive variant is the same minus the voting block."""
    blocks = converter._paper_to_blocks(enriched(1)[0], 1)

    assert len(blocks) == 3
    assert [b["type"] for b in blocks] == ["section", "section", "divider"]


def test_methodology_and_contributions_are_not_rendered():
    """Both were dropped in favour of delta and benchmark lines."""
    body = converter._paper_body_text(enriched(1)[0])

    assert "방법론" not in body
    assert "핵심 기여" not in body
    assert "🔀 *델타*" in body


# --- total budget ---------------------------------------------------------


def test_total_blocks_under_limit_for_ten_papers():
    """Ten deep papers plus a full skim list must still fit in one message."""
    blocks = converter.to_slack_blocks_interactive(
        enriched(10), "2026-08-21", None, [skim(f"2602.{i:05d}") for i in range(11)]
    )

    assert len(blocks) == 3 + 4 * 10 + 1
    assert len(blocks) <= SLACK_BLOCK_LIMIT


def test_section_text_under_3000():
    """No section may exceed Slack's per-section character cap."""
    blocks = converter.to_slack_blocks_interactive(
        enriched(10), "2026-08-21", None, [skim(f"2602.{i:05d}") for i in range(11)]
    )

    sections = [b for b in blocks if b["type"] == "section" and "text" in b]
    assert sections
    for block in sections:
        assert len(block["text"]["text"]) <= SECTION_TEXT_LIMIT


# --- fallback -------------------------------------------------------------


def test_json_fallback_keeps_block_count():
    """A paper with no analysis directory still renders as four blocks."""
    fallback = enrich.enrich_papers([paper("2602.06540")], loader=lambda _: None)[0]

    assert fallback.delta_axes == []
    assert fallback.verification is None
    assert fallback.headline == "markdown summary"
    assert len(converter._paper_to_blocks_interactive(fallback, 1, "2026-02-10")) == 4


def test_enrichment_survives_a_broken_loader():
    """A failing loader degrades to markdown-only, it does not sink the message."""
    def explode(_arxiv_id):
        raise OSError("unreadable")

    fallback = enrich.enrich_papers([paper()], loader=explode)[0]

    assert fallback.delta_axes == []
    assert len(converter._paper_to_blocks_interactive(fallback, 1, "2026-08-21")) == 4


# --- vote contract --------------------------------------------------------


def test_vote_button_value_format_unchanged():
    """action_id and value are parsed by server.handle_vote_action - do not drift."""
    enriched_paper = enriched(1)[0]
    blocks = converter._paper_to_blocks_interactive(enriched_paper, 2, "2026-08-21")
    actions = next(b for b in blocks if b["type"] == "actions")

    assert actions["block_id"] == f"vote-2-{enriched_paper.arxiv_id}"
    assert [e["action_id"] for e in actions["elements"]] == [
        "vote_applicable", "vote_idea", "vote_pass", "add_comment",
    ]
    expected = f"2026-08-21|{enriched_paper.arxiv_id}|{enriched_paper.title}"
    for element in actions["elements"]:
        assert element["value"] == expected
