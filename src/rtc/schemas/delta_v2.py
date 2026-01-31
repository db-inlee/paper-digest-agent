"""Delta 스키마 v2 - CoreDelta 기반."""

from typing import Optional

from pydantic import BaseModel, Field

from rtc.schemas.extraction_v2 import Evidence


class CoreDelta(BaseModel):
    """구조적 변화 기록."""

    axis: str = Field(
        ...,
        description="변화 축 (예: control_paradigm, memory_structure, inference_strategy)",
    )
    old_approach: str = Field(..., description="기존 접근법")
    new_approach: str = Field(..., description="새로운 접근법")
    why_better: str = Field(..., description="왜 더 나은지 (구체적으로)")
    evidence: Evidence = Field(..., description="근거")


class TradeoffWithEvidence(BaseModel):
    """트레이드오프 (Evidence 포함)."""

    aspect: str = Field(..., description="측면 (예: latency, accuracy, cost)")
    benefit: str = Field(..., description="이점")
    cost: str = Field(..., description="비용/단점")
    when_acceptable: Optional[str] = Field(
        default=None, description="언제 수용 가능한지"
    )
    evidence: Evidence = Field(..., description="근거")


class DeltaOutput(BaseModel):
    """Delta Agent 출력 - delta.json 스키마."""

    arxiv_id: str = Field(..., description="arXiv ID")
    one_line_takeaway: str = Field(
        ...,
        description=(
            "한 줄 요약: '이 논문은 [기존 방법 X]의 [구조적 한계 A]를 "
            "[핵심 변화 B]를 [단계]에서 도입하여 해결했다' 형식"
        ),
    )
    core_deltas: list[CoreDelta] = Field(
        ..., min_length=1, description="핵심 구조적 변화 (최소 1개)"
    )
    tradeoffs: list[TradeoffWithEvidence] = Field(
        default_factory=list, description="트레이드오프"
    )
    when_to_use: str = Field(..., description="언제 이 방법을 사용해야 하는지")
    when_not_to_use: str = Field(..., description="언제 사용하지 말아야 하는지")

    @property
    def delta_count(self) -> int:
        """Delta 개수."""
        return len(self.core_deltas)

    @property
    def has_tradeoffs(self) -> bool:
        """트레이드오프 존재 여부."""
        return len(self.tradeoffs) > 0

    def get_primary_delta(self) -> CoreDelta:
        """가장 중요한 Delta 반환."""
        return self.core_deltas[0]
