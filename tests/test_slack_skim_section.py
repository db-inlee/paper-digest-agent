"""The skim list is one block, and every send path still carries it."""

import inspect

import pytest

converter = pytest.importorskip("toslack.converter")
models = pytest.importorskip("toslack.models")


def skim(index: int, one_liner: str = "a short summary") -> models.SkimPaper:
    return models.SkimPaper(
        title=f"Skim Paper {index}",
        arxiv_url=f"https://arxiv.org/abs/2602.{index:05d}",
        matched_keywords=["agent", "rl", "llm", "dropped"],
        category="agent",
        one_liner=one_liner,
    )


def test_skim_section_is_single_block():
    """Eleven skim papers used to cost 24 blocks; they now cost one."""
    blocks = converter._skim_papers_to_blocks([skim(i) for i in range(11)])

    assert len(blocks) == 1
    assert blocks[0]["type"] == "section"
    text = blocks[0]["text"]["text"]
    assert "기타 주목할 논문 (11편)" in text
    assert text.count("\n") == 11


def test_skim_entry_caps_keywords_and_one_liner():
    text = converter._skim_papers_to_blocks([skim(1, "가" * 200)])[0]["text"]["text"]

    assert "`dropped`" not in text
    assert "…" in text


def test_skim_section_truncates_over_limit():
    """Over the section cap the tail is folded, and the fold is stated."""
    papers = [skim(i, "가" * 120) for i in range(200)]
    text = converter._skim_papers_to_blocks(papers)[0]["text"]["text"]

    assert len(text) <= converter.SECTION_TEXT_LIMIT
    assert "… 외 " in text and "편" in text


def test_both_block_variants_render_the_skim_section():
    """to_slack_blocks and its interactive twin must not diverge here."""
    papers: list[models.PaperSummary] = []
    skims = [skim(i) for i in range(5)]

    assert len(converter.to_slack_blocks(papers, "2026-08-21", skims)) == 3 + 1
    assert len(converter.to_slack_blocks_interactive(papers, "2026-08-21", None, skims)) == 3 + 1


def test_every_send_path_passes_skim_papers():
    """A path that drops skim_papers deletes the list from the posted message.

    server.update_message_votes rebuilds the whole message on each vote, so an
    omission there erases the skim section on the first click.
    """
    cli = pytest.importorskip("toslack.cli")
    server = pytest.importorskip("toslack.server")

    send = inspect.getsource(cli.send)
    assert "to_slack_payload_interactive(papers, date, vote_counts, skim_papers)" in send
    assert "to_slack_payload(papers, date, skim_papers)" in send

    update = inspect.getsource(server.update_message_votes)
    assert "to_slack_blocks_interactive(papers, report_date, vote_counts, skim_papers)" in update

    report = inspect.getsource(server._send_report_to_slack)
    assert "skim_papers)" in report
