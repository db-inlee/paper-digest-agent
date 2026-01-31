"""CorrectionAgent - 교정 에이전트 (LLM)."""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.delta_v2 import CoreDelta, DeltaOutput, TradeoffWithEvidence
from rtc.schemas.extraction_v2 import ClaimWithEvidence, ExtractionOutput
from rtc.schemas.verification_v1 import VerificationOutput


@dataclass
class CorrectionInput:
    """Correction 입력."""

    arxiv_id: str
    title: str
    abstract: str
    full_text: Optional[str]
    extraction: ExtractionOutput
    delta: DeltaOutput
    verification: VerificationOutput


class CorrectedClaim(BaseModel):
    """수정된 클레임."""

    claim_id: str = Field(..., description="클레임 ID")
    corrected_text: str = Field(..., description="수정된 클레임 내용")
    correction_reason: str = Field(..., description="수정 이유 (한국어)")


class CorrectedDelta(BaseModel):
    """수정된 Delta."""

    axis: str = Field(..., description="변화 축")
    old_approach: str = Field(..., description="수정된 기존 접근법")
    new_approach: str = Field(..., description="수정된 새로운 접근법")
    why_better: str = Field(..., description="수정된 이유")
    correction_reason: str = Field(..., description="수정 이유 (한국어)")


class CorrectionResult(BaseModel):
    """교정 결과 스키마."""

    arxiv_id: str = Field(..., description="arXiv ID")
    corrected_claims: list[CorrectedClaim] = Field(
        default_factory=list, description="수정된 클레임 목록"
    )
    corrected_deltas: list[CorrectedDelta] = Field(
        default_factory=list, description="수정된 Delta 목록"
    )
    correction_summary: str = Field(..., description="교정 요약 (한국어)")


@dataclass
class CorrectionOutput:
    """Correction 에이전트 출력."""

    extraction: ExtractionOutput
    delta: DeltaOutput
    correction_summary: str


CORRECTION_SYSTEM_PROMPT = """You are a Correction Agent fixing inaccuracies in extracted research paper analysis.

## 출력 언어 규칙 (중요!)
- 모든 출력은 반드시 한국어로 작성 (corrected_text 포함)
- 고유명사(모델명, 알고리즘명)만 영어 유지

## 교정 원칙
1. 논문 원문에 근거하여 수정
2. 모호한 내용은 더 정확하게 작성
3. 잘못된 내용은 올바른 내용으로 교체
4. 근거 없는 주장은 삭제하거나 완화

## 교정 대상
- corrections_needed에 포함된 claim_id만 수정
- delta:{axis} 형식이면 해당 delta 수정

## 수정 규칙
1. 기존 claim_id 유지
2. claim_type 변경 금지
3. 수정 이유 명시"""

CORRECTION_PROMPT_TEMPLATE = """Fix the inaccuracies identified in the verification.

**Paper**: {title} ({arxiv_id})

**Abstract**:
{abstract}

**Full Text**:
{full_text}

---

## Corrections Needed:
{corrections_needed}

## Verification Results with Hints:
{verification_hints}

---

## Current Claims:
{claims_text}

## Current Deltas:
{deltas_text}

---

## Instructions:
1. corrections_needed에 있는 항목만 수정
2. 각 수정에 대해 논문 근거 제시
3. correction_reason에 왜 수정했는지 한국어로 설명

Output corrected items in the specified JSON schema."""


class CorrectionAgent(BaseAgent[CorrectionInput, CorrectionOutput]):
    """교정 에이전트 (LLM)."""

    name = "correction"
    uses_llm = True

    def __init__(self):
        self.settings = get_settings()

    async def run(self, input: CorrectionInput) -> CorrectionOutput:
        """검증 실패 항목 교정.

        Args:
            input: 교정 입력

        Returns:
            교정된 extraction, delta
        """
        verification = input.verification

        # 교정 필요 없으면 원본 반환
        if not verification.corrections_needed:
            return CorrectionOutput(
                extraction=input.extraction,
                delta=input.delta,
                correction_summary="교정 필요 없음",
            )

        model = self.settings.agent_models.get("correction", "gpt-4o-mini")
        llm = get_llm_client(provider="openai", model=model)

        extraction = input.extraction
        delta = input.delta

        # Claims 텍스트 준비
        claims_text = "\n".join(
            f"- [{c.claim_id}] ({c.claim_type}) {c.text}"
            for c in extraction.claims
        )

        # Delta 텍스트 준비
        deltas_text = "\n".join(
            f"- [{d.axis}] {d.old_approach} → {d.new_approach}: {d.why_better}"
            for d in delta.core_deltas
        )

        # Verification hints 준비
        verification_hints = "\n".join(
            f"- [{r.claim_id}] {r.status}: {r.notes}"
            + (f"\n  Hint: {r.correction_hint}" if r.correction_hint else "")
            for r in verification.results
            if r.status in ("contradicted", "unverified")
        )

        # Corrections needed
        corrections_needed = "\n".join(
            f"- {item}" for item in verification.corrections_needed
        )

        # Full text 처리
        full_text = input.full_text or "(Full text not available)"
        if len(full_text) > 50000:
            full_text = full_text[:50000] + "\n... (truncated)"

        prompt = CORRECTION_PROMPT_TEMPLATE.format(
            title=input.title,
            arxiv_id=input.arxiv_id,
            abstract=input.abstract,
            full_text=full_text,
            corrections_needed=corrections_needed or "(None)",
            verification_hints=verification_hints or "(None)",
            claims_text=claims_text or "(No claims)",
            deltas_text=deltas_text,
        )

        try:
            result = await llm.generate_structured(
                prompt=prompt,
                output_schema=CorrectionResult,
                system_prompt=CORRECTION_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=4000,
            )

            # 결과 병합
            corrected_extraction = self._apply_claim_corrections(
                extraction, result.corrected_claims
            )
            corrected_delta = self._apply_delta_corrections(
                delta, result.corrected_deltas
            )

            return CorrectionOutput(
                extraction=corrected_extraction,
                delta=corrected_delta,
                correction_summary=result.correction_summary,
            )

        except Exception as e:
            # 실패 시 원본 반환
            return CorrectionOutput(
                extraction=input.extraction,
                delta=input.delta,
                correction_summary=f"교정 실패: {str(e)}",
            )

    def _apply_claim_corrections(
        self, extraction: ExtractionOutput, corrections: list[CorrectedClaim]
    ) -> ExtractionOutput:
        """클레임 교정 적용."""
        if not corrections:
            return extraction

        # claim_id → corrected_text 매핑
        correction_map = {c.claim_id: c.corrected_text for c in corrections}

        # 새로운 claims 리스트 생성
        new_claims = []
        for claim in extraction.claims:
            if claim.claim_id in correction_map:
                # 수정된 클레임 생성
                new_claims.append(
                    ClaimWithEvidence(
                        claim_id=claim.claim_id,
                        text=correction_map[claim.claim_id],
                        claim_type=claim.claim_type,
                        confidence=claim.confidence,
                        evidence=claim.evidence,
                    )
                )
            else:
                new_claims.append(claim)

        # 새 ExtractionOutput 생성
        return ExtractionOutput(
            arxiv_id=extraction.arxiv_id,
            title=extraction.title,
            problem_definition=extraction.problem_definition,
            baselines=extraction.baselines,
            method_components=extraction.method_components,
            benchmark=extraction.benchmark,
            claims=new_claims,
            extraction_mode=extraction.extraction_mode,
        )

    def _apply_delta_corrections(
        self, delta: DeltaOutput, corrections: list[CorrectedDelta]
    ) -> DeltaOutput:
        """Delta 교정 적용."""
        if not corrections:
            return delta

        # axis → correction 매핑
        correction_map = {c.axis: c for c in corrections}

        # 새로운 core_deltas 리스트 생성
        new_deltas = []
        for d in delta.core_deltas:
            if d.axis in correction_map:
                corr = correction_map[d.axis]
                new_deltas.append(
                    CoreDelta(
                        axis=d.axis,
                        old_approach=corr.old_approach,
                        new_approach=corr.new_approach,
                        why_better=corr.why_better,
                        evidence=d.evidence,
                    )
                )
            else:
                new_deltas.append(d)

        # 새 DeltaOutput 생성
        return DeltaOutput(
            arxiv_id=delta.arxiv_id,
            one_line_takeaway=delta.one_line_takeaway,
            core_deltas=new_deltas,
            tradeoffs=delta.tradeoffs,
            when_to_use=delta.when_to_use,
            when_not_to_use=delta.when_not_to_use,
        )
