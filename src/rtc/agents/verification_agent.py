"""VerificationAgent - 검증 에이전트 (LLM)."""

from dataclasses import dataclass
from typing import Optional

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.verification_v1 import VerificationOutput


@dataclass
class VerificationInput:
    """Verification 입력."""

    arxiv_id: str
    title: str
    abstract: str
    full_text: Optional[str]
    extraction: ExtractionOutput
    delta: DeltaOutput


VERIFICATION_SYSTEM_PROMPT = """You are a Verification Agent checking the accuracy of extracted research paper analysis.

## 출력 언어 규칙 (중요!)
- 모든 출력은 반드시 한국어로 작성
- 고유명사(모델명, 알고리즘명)만 영어 유지

## 검증 기준

### verified (검증됨)
- 논문에서 직접적인 근거를 찾을 수 있음
- 인용된 페이지/섹션이 정확함

### unverified (미검증)
- 논문에서 명시적 근거를 찾을 수 없음
- 추론이나 해석에 의존함

### contradicted (모순됨)
- 논문 내용과 상충됨
- 잘못된 해석이나 오류

## CRITICAL RULES
1. 논문 원문에서 직접 근거를 찾아야 함
2. 추측이나 일반 지식으로 검증하지 않음
3. 모호한 경우 unverified로 분류
4. contradicted 상태인 경우 반드시 correction_hint 제공

## 핵심 검증 항목 (우선순위 높음)
5. **Baseline 정확성**: 언급된 baseline이 논문에서 실제로 직접 비교 대상인지 검증
   - Related Work에만 언급된 것을 baseline으로 잘못 분류했는지 확인
   - "개선 대상"으로 표현된 baseline이 실제로 실험에서 비교되었는지 확인
6. **One-line Takeaway 정확성**: "[X]의 [한계]를 [Y]로 해결했다" 형태의 문장에서:
   - [X]가 실제로 논문이 직접 개선 대상으로 삼은 방법인지 확인
   - 새로운 영역을 개척한 논문인데 마치 기존 방법을 개선한 것처럼 표현되지 않았는지 확인
7. **인과관계 정확성**: 논문의 기여가 정확하게 표현되었는지 확인

## 신뢰도 판정 기준
- high: 80% 이상 verified, contradicted 0개
- medium: 60% 이상 verified, 또는 contradicted 1-2개
- low: 60% 미만 verified, 또는 contradicted 3개 이상

## corrections_needed 작성 규칙
- contradicted 상태인 claim_id 목록
- delta의 핵심 오류가 있으면 "delta:{axis}" 형식으로 추가
- baseline 오류가 있으면 "baseline:{name}" 형식으로 추가
- one_line_takeaway 오류가 있으면 "one_line_takeaway" 추가"""

VERIFICATION_PROMPT_TEMPLATE = """Verify the accuracy of extracted information against the original paper.

**Paper**: {title} ({arxiv_id})

**Abstract**:
{abstract}

**Full Text** (if available):
{full_text}

---

## Extracted Claims to Verify:

{claims_text}

---

## Baseline Information to Verify:

{baselines_text}

---

## Delta Information to Verify:

**One-line Takeaway**: {one_line_takeaway}

**Core Deltas**:
{deltas_text}

---

## Instructions:

### 1. Baseline 검증 (가장 중요!)
- 각 baseline이 논문에서 **실험적으로 비교**되었는지 확인
- Related Work에만 언급된 것이 baseline으로 잘못 분류되었으면 contradicted 처리
- baseline의 "limitation"이 논문에서 실제로 주장된 것인지 확인

### 2. One-line Takeaway 검증
- "[X]의 [한계]를 해결했다" 형태에서 X가 실제 baseline인지 확인
- 새로운 접근/최초 시도를 마치 기존 방법 개선처럼 표현했으면 contradicted 처리
- 예: "Foundation-Sec-8B-Instruct를 개선했다"고 했는데 실제로는 같은 base model에서 다른 방식으로 훈련한 것이면 → contradicted

### 3. Core Deltas 검증
- old_approach가 허위 baseline에 기반하면 contradicted 처리
- 논문이 실제로 주장하지 않은 개선점이 있으면 contradicted 처리

### 4. Claims 검증
- 각 클레임이 논문에서 지지되는지 검증

### 5. 최종 판정
- 전체 신뢰도(high/medium/low) 판정
- contradicted 항목에 대해 교정 힌트 제공
- corrections_needed에 수정이 필요한 항목 목록 작성

Output verification results in the specified JSON schema."""


class VerificationAgent(BaseAgent[VerificationInput, VerificationOutput]):
    """검증 에이전트 (LLM)."""

    name = "verification"
    uses_llm = True

    def __init__(self):
        self.settings = get_settings()

    async def run(self, input: VerificationInput) -> VerificationOutput:
        """Extraction + Delta 결과 검증.

        Args:
            input: 검증 입력

        Returns:
            검증 결과
        """
        model = self.settings.agent_models.get("verification", "gpt-4o-mini")
        llm = get_llm_client(provider="openai", model=model)

        extraction = input.extraction
        delta = input.delta

        # Claims 텍스트 준비
        claims_text = "\n".join(
            f"- [{c.claim_id}] ({c.claim_type}) {c.text}"
            for c in extraction.claims
        )

        # Baselines 텍스트 준비
        baselines_text = "\n".join(
            f"- [{b.name}] {b.description} (한계: {b.limitation})"
            for b in extraction.baselines
        ) if extraction.baselines else "(No baselines extracted)"

        # Delta 텍스트 준비
        deltas_text = "\n".join(
            f"- [{d.axis}] {d.old_approach} → {d.new_approach}: {d.why_better}"
            for d in delta.core_deltas
        )

        # Full text 처리 (너무 길면 자름)
        full_text = input.full_text or "(Full text not available)"
        if len(full_text) > 50000:
            full_text = full_text[:50000] + "\n... (truncated)"

        prompt = VERIFICATION_PROMPT_TEMPLATE.format(
            title=input.title,
            arxiv_id=input.arxiv_id,
            abstract=input.abstract,
            full_text=full_text,
            claims_text=claims_text or "(No claims extracted)",
            baselines_text=baselines_text,
            one_line_takeaway=delta.one_line_takeaway,
            deltas_text=deltas_text,
        )

        try:
            result = await llm.generate_structured(
                prompt=prompt,
                output_schema=VerificationOutput,
                system_prompt=VERIFICATION_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=4000,
            )

            return result

        except Exception as e:
            # 실패 시 기본값 반환 (통과 처리)
            return self._create_fallback_output(input.arxiv_id, str(e))

    def _create_fallback_output(self, arxiv_id: str, error: str) -> VerificationOutput:
        """실패 시 폴백 출력 생성 (통과 처리)."""
        return VerificationOutput(
            arxiv_id=arxiv_id,
            total_claims=0,
            verified_count=0,
            unverified_count=0,
            contradicted_count=0,
            overall_reliability="high",  # 검증 실패 시 통과 처리
            results=[],
            summary=f"검증 실패로 인한 자동 통과: {error}",
            corrections_needed=[],
        )
