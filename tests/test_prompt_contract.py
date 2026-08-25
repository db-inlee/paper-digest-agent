"""Prompt and wiring contracts for the extraction/delta agents.

Prompt quality cannot be asserted without calling a model, but the specific
regressions this project has already suffered can be:

- ``role`` was absent from the extraction prompt, so 39.6% of components had no
  value at all and the field was useless as a signal.
- The delta prompt handed the model the exact string
  "해당 영역에 특화된 방법 없음" to use when baselines were empty, and it showed up
  in 15 of 89 delta axes.
- ``delta_node`` never received the paper text, so evidence quotes could only be
  copies of our own Korean summaries (94% self-referential).

These tests pin the fixes so a later prompt edit cannot silently undo them.
"""

import inspect

import pytest

delta_agent = pytest.importorskip("rtc.agents.delta_agent")
extraction = pytest.importorskip("rtc.agents.extraction")
deep = pytest.importorskip("rtc.pipeline.deep")

DELTA_PROMPT = delta_agent.DELTA_SYSTEM_PROMPT + delta_agent.DELTA_PROMPT_TEMPLATE
EXTRACTION_PROMPT = (
    extraction.EXTRACTION_SYSTEM_PROMPT + extraction.EXTRACTION_PROMPT_TEMPLATE
)

# The four exact strings observed in delta.json across the corpus.
BOILERPLATE = (
    "해당 영역에 특화된 방법 없음",
    "해당 없음",
    "기존에 특화된 해결책 없음",
    "일반적인 기존 접근",
)


def _instruction_text() -> str:
    """Prompt text with the BAD-EXAMPLES block removed.

    The boilerplate strings are legitimately listed there as things *not* to
    write; everywhere else they are an instruction to write them.
    """
    marker = "## BAD DELTA EXAMPLES"
    head, _, tail = DELTA_PROMPT.partition(marker)
    # Keep whatever follows the bad-example bullets (the user template).
    rest = tail.split("\n\n", 1)
    return head + (rest[1] if len(rest) > 1 else "")


# --- P2: boilerplate removed, hallucination guard kept --------------------


@pytest.mark.parametrize("phrase", BOILERPLATE)
def test_delta_prompt_does_not_prescribe_boilerplate_old_approach(phrase):
    assert phrase not in _instruction_text()


def test_delta_prompt_still_forbids_inventing_baselines():
    """Demanding specificity must not turn into a licence to hallucinate."""
    assert "허위 baseline" in DELTA_PROMPT
    assert "fabricate하지 말 것" in DELTA_PROMPT


def test_delta_prompt_lists_boilerplate_as_a_bad_example():
    bad_block = DELTA_PROMPT.split("## BAD DELTA EXAMPLES")[1]
    assert "해당 영역에 특화된 방법 없음" in bad_block


# --- P1: role is requested, with all three values and a mixed example -----


def test_extraction_prompt_requires_role_with_all_three_values():
    template = extraction.EXTRACTION_PROMPT_TEMPLATE
    assert "role" in template
    for value in ("novel", "adapted", "standard"):
        assert value in template


def test_role_example_does_not_label_everything_novel():
    """An all-novel example teaches the model to collapse the field."""
    template = extraction.EXTRACTION_PROMPT_TEMPLATE
    example = template.split("예시 (Transformer 논문의 경우")[1]
    for value in ("novel", "adapted", "standard"):
        assert f"role: {value}" in example, value


# --- P4: baseline_methods requested ---------------------------------------


def test_extraction_prompt_requests_baseline_methods():
    assert "baseline_methods" in extraction.EXTRACTION_PROMPT_TEMPLATE


# --- P3: full text reaches the delta agent --------------------------------


def test_delta_agent_accepts_optional_full_text():
    signature = inspect.signature(delta_agent.DeltaAgent.run)
    assert "full_text" in signature.parameters
    assert signature.parameters["full_text"].default is None


def test_delta_node_passes_full_text_from_parsed_pdf():
    source = inspect.getsource(deep.delta_node)
    assert "parsed_pdf" in source
    assert "get_full_text()" in source
    assert "full_text=full_text" in source


def test_delta_full_text_limit_matches_verification():
    """Same budget as the other agents that quote from the paper."""
    verification = pytest.importorskip("rtc.agents.verification_agent")
    assert delta_agent.FULL_TEXT_CHAR_LIMIT == 50000
    assert "50000" in inspect.getsource(verification.VerificationAgent.run)


def test_delta_prompt_demands_verbatim_quotes_and_empty_without_source():
    assert "verbatim" in DELTA_PROMPT
    assert "재사용하지 마세요" in DELTA_PROMPT
    assert "비워" in DELTA_PROMPT
