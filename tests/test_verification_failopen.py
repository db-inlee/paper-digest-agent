"""Regression tests for the verification fail-open fix.

Pins down (without any LLM call) that a failed verification fails *closed*
instead of being disguised as a high-quality verdict, and that routing skips
the correction loop on verification errors.
"""

from rtc.agents.verification_agent import VerificationAgent, VerificationInput
from rtc.pipeline.deep import should_retry_or_proceed
from rtc.schemas.delta_v2 import CoreDelta, DeltaOutput
from rtc.schemas.extraction_v2 import (
    ClaimWithEvidence,
    Evidence,
    ExtractionOutput,
    MethodComponent,
    ProblemDefinition,
)
from rtc.schemas.verification_v1 import VerificationOutput


def _vout(reliability: str, error: bool) -> VerificationOutput:
    return VerificationOutput(
        arxiv_id="1234.5678",
        total_claims=0,
        verified_count=0,
        unverified_count=0,
        contradicted_count=0,
        overall_reliability=reliability,
        results=[],
        summary="test",
        corrections_needed=[],
        verification_error=error,
    )


def test_fallback_fails_closed_not_high():
    out = VerificationAgent()._create_fallback_output("1234.5678", "boom")
    assert out.overall_reliability != "high"
    assert out.overall_reliability == "low"
    assert out.verification_error is True


def test_routing_skips_correction_on_verification_error():
    # retry budget is available, but a verification error must skip correction
    state = {
        "verification": _vout("low", error=True),
        "retry_count": 0,
        "max_retries": 2,
    }
    assert should_retry_or_proceed(state) == "report"


def test_routing_preserves_real_low_correction_path():
    # genuine low-quality verdict (no error) still goes to correction
    state = {
        "verification": _vout("low", error=False),
        "retry_count": 0,
        "max_retries": 2,
    }
    assert should_retry_or_proceed(state) == "correction"


def test_routing_high_goes_to_report():
    state = {
        "verification": _vout("high", error=False),
        "retry_count": 0,
        "max_retries": 2,
    }
    assert should_retry_or_proceed(state) == "report"


class _FakeLLM:
    """LLM stub whose structured output hallucinates verification_error=True."""

    async def generate_structured(self, **kwargs):
        return _vout("high", error=True)


def _vinput() -> VerificationInput:
    extraction = ExtractionOutput(
        arxiv_id="1234.5678",
        title="T",
        problem_definition=ProblemDefinition(statement="p", structural_limitation="l"),
        method_components=[MethodComponent(name="M1", description="d1")],
        claims=[ClaimWithEvidence(claim_id="C1", text="t", claim_type="method")],
    )
    delta = DeltaOutput(
        arxiv_id="1234.5678",
        one_line_takeaway="t",
        core_deltas=[
            CoreDelta(
                axis="a",
                old_approach="o",
                new_approach="n",
                why_better="w",
                evidence=Evidence(quote="q", type="quote"),
            )
        ],
        when_to_use="u",
        when_not_to_use="a",
    )
    return VerificationInput(
        arxiv_id="1234.5678",
        title="T",
        abstract="abstract",
        full_text=None,
        extraction=extraction,
        delta=delta,
    )


async def test_successful_run_forces_verification_error_false(monkeypatch):
    # change 2.5: even if the model returns verification_error=True on a
    # successful run, run() must force it back to False (anti-hallucination).
    monkeypatch.setattr(
        "rtc.agents.verification_agent.get_llm_client", lambda **kw: _FakeLLM()
    )
    out = await VerificationAgent().run(_vinput())
    assert out.verification_error is False
