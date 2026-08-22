"""No claim may be dropped because its type has no Korean label."""

import typing

from rtc.agents.daily_report_agent import DailyReportAgent
from rtc.agents.report_writer import ReportWriter
from rtc.schemas.extraction_v2 import (
    CLAIM_TYPE_LABELS,
    ClaimWithEvidence,
    ExtractionOutput,
    MethodComponent,
    ProblemDefinition,
)

SCHEMA_TYPES = typing.get_args(
    ClaimWithEvidence.model_fields["claim_type"].annotation
)


def extraction(claim_types: list[str]) -> ExtractionOutput:
    return ExtractionOutput(
        arxiv_id="2608.00001",
        title="Paper",
        problem_definition=ProblemDefinition(statement="문제", structural_limitation="한계"),
        method_components=[
            MethodComponent(name="C1", description="설명1"),
            MethodComponent(name="C2", description="설명2"),
        ],
        claims=[
            ClaimWithEvidence(
                claim_id=f"c{i}", text=f"클레임 {i} ({t})", claim_type=t, confidence=1.0
            )
            for i, t in enumerate(claim_types, 1)
        ],
    )


def render_daily(ex: ExtractionOutput) -> str:
    return "\n".join(DailyReportAgent()._render_claims_section(ex))


# --- B1. unmapped types are rendered --------------------------------------


def test_unmapped_claim_type_is_rendered():
    """감사에서 소실이 확인된 architecture/efficiency가 출력에 남는다."""
    text = render_daily(extraction(["method", "architecture", "efficiency"]))

    assert "클레임 2 (architecture)" in text
    assert "클레임 3 (efficiency)" in text


def test_no_claim_is_dropped():
    """입력 클레임 수 == 출력 항목 수."""
    types = ["method", "result", "comparison", "limitation", "architecture", "efficiency"]
    text = render_daily(extraction(types))

    assert len([ln for ln in text.splitlines() if ln.startswith("- ")]) == len(types)


def test_all_schema_claim_types_are_covered():
    """스키마 Literal 7종 각각이 라벨을 갖고, 각각의 클레임이 렌더된다."""
    assert set(SCHEMA_TYPES) == set(CLAIM_TYPE_LABELS)

    text = render_daily(extraction(list(SCHEMA_TYPES)))
    for i, claim_type in enumerate(SCHEMA_TYPES, 1):
        assert f"클레임 {i} ({claim_type})" in text
        assert f"### {CLAIM_TYPE_LABELS[claim_type]}" in text


def test_daily_and_deep_renderers_agree_on_labels():
    """두 렌더러가 같은 claim_type에 같은 헤딩을 쓴다 (미매핑 폴백 포함)."""
    ex = extraction(["method", "architecture"])
    daily = render_daily(ex)
    deep = ReportWriter()._format_claims(ex)

    for claim_type in ("method", "architecture"):
        heading = f"### {CLAIM_TYPE_LABELS.get(claim_type, claim_type)}"
        assert heading in daily
        assert heading in deep


def test_type_outside_the_schema_still_renders():
    """스키마에도 없는 값이 와도 원문 그대로 남는다 (라벨은 필터가 아니다)."""
    ex = extraction(["method"])
    ex.claims[0].claim_type = "brand_new_type"  # 검증 없이 주입

    text = render_daily(ex)

    assert "### brand_new_type" in text
    assert "클레임 1 (method)" in text
