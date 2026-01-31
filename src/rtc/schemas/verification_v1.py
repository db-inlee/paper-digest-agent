"""Verification 스키마 v1 - 검증 결과."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    """개별 클레임 검증 결과."""

    claim_id: str = Field(..., description="클레임 ID")
    claim_text: str = Field(..., description="클레임 내용")
    status: Literal["verified", "unverified", "contradicted"] = Field(
        ..., description="검증 상태"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="검증 신뢰도"
    )
    evidence_found: Optional[str] = Field(
        default=None, description="찾은 근거"
    )
    notes: str = Field(..., description="검증 설명 (한국어)")
    correction_hint: Optional[str] = Field(
        default=None, description="교정 힌트 (틀린 경우)"
    )


class VerificationOutput(BaseModel):
    """검증 에이전트 출력 - verification.json 스키마."""

    arxiv_id: str = Field(..., description="arXiv ID")
    total_claims: int = Field(..., description="총 클레임 수")
    verified_count: int = Field(..., description="검증된 클레임 수")
    unverified_count: int = Field(..., description="미검증 클레임 수")
    contradicted_count: int = Field(..., description="모순된 클레임 수")
    overall_reliability: Literal["high", "medium", "low"] = Field(
        ..., description="전체 신뢰도"
    )
    results: list[VerificationResult] = Field(
        default_factory=list, description="개별 검증 결과"
    )
    summary: str = Field(..., description="전체 요약 (한국어)")
    corrections_needed: list[str] = Field(
        default_factory=list, description="교정 필요한 항목 목록"
    )

    @property
    def verification_rate(self) -> float:
        """검증률."""
        if self.total_claims == 0:
            return 1.0
        return self.verified_count / self.total_claims

    @property
    def needs_correction(self) -> bool:
        """교정 필요 여부."""
        return len(self.corrections_needed) > 0
