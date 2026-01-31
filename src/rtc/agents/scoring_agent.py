"""ScoringAgent - 실용성 평가 (LLM)."""

from dataclasses import dataclass

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.scoring_v2 import ScoringOutput


@dataclass
class ScoringInput:
    """Scoring 입력."""

    extraction: ExtractionOutput
    delta: DeltaOutput


SCORING_SYSTEM_PROMPT = """You are an expert evaluating research papers for practical implementation.

## 목적 (중요!)
이 평가의 목적은 논문을 깊이 리뷰하는 것이 아닙니다.
"최근 연구 트렌드가 어떤 방향으로 가고 있는지"를 감지하기 위한 데일리 리포트입니다.

## 출력 언어 규칙 (중요!)
- reasoning, key_strength, main_concern은 반드시 한국어로 작성해야 합니다
- 아래 점수 기준은 참고용이며, 출력은 모두 한국어로 작성
- 고유명사(모델명, 데이터셋명)만 영어 유지
- 영어 전문 용어는 한국어(영어) 형태로 병기

## 정확성 가이드 (반드시 지킬 것)

### 과장 표현 금지
reasoning, key_strength 등에서 다음과 같은 단정적 표현을 사용하지 않습니다:
- "해결했다", "자동화했다", "보장한다", "최초다", "혁신적이다"
대신 아래와 같은 완화된 표현을 사용합니다:
- "~을 제안한다"
- "~을 개선한다"
- "~을 지원한다"
- "~을 목표로 한다"
- "~의 가능성을 보여준다"

### 확장 해석 금지
논문이 직접 언급하지 않은 상위 해석을 추가하지 않습니다.
반드시 논문에서 명시적으로 언급한 범위까지만 평가합니다.

## SCORING CRITERIA (Each 0-5)

### Practicality (실용성)
- 0: 순수 이론, 실용적 가치 없음
- 1: 잠재적 응용 가능성 있음
- 2: 일부 실용적 응용 가능
- 3: 명확한 실용적 응용 가능
- 4: 즉시 적용 가능, 실제 문제 해결 가능성
- 5: 높은 실용성, 광범위한 적용 가능

### Codeability (구현 가능성)
- 0: 구현 불가능 수준의 복잡도
- 1: 전문 인프라 필요, 매우 복잡
- 2: 상당한 전문성 필요
- 3: 중간 복잡도, 구현 가능
- 4: 명확한 알고리즘, 쉬운 구현
- 5: 즉시 구현 가능, 코드 제공됨

### Signal (신뢰도)
- 0: 결과 없거나 신뢰 불가
- 1: 약한 결과, 불명확
- 2: 일부 제한적 결과
- 3: 합리적 결과, 일부 한계
- 4: 강력한 결과, 잘 뒷받침됨
- 5: 매우 강력한 결과, 완벽한 근거

## RECOMMENDATION THRESHOLDS
- must_read: total >= 12 (강력 추천)
- worth_reading: total >= 8 (읽어볼 만함)
- skip: total < 8 (스킵 가능)

Be honest and critical. Don't inflate scores.
결과를 단정적으로 서술하지 않습니다."""

SCORING_PROMPT_TEMPLATE = """Evaluate this paper for practical implementation.

**Paper**: {title} ({arxiv_id})

**One-line Takeaway**: {one_line_takeaway}

**Problem**: {problem_statement}

**Key Deltas**:
{deltas_text}

**Evidence Coverage**: {evidence_coverage}%

**Claims Count**: {claims_count}

Score this paper on:
1. **practicality** (0-5): 실용성 - 실제 문제 해결 가능성
2. **codeability** (0-5): 구현 가능성 - 코드로 만들기 쉬운 정도
3. **signal** (0-5): 신뢰도 - 결과/주장의 근거 강도

Then provide:
- **recommendation**: must_read / worth_reading / skip
- **reasoning**: 점수 판단 근거 (한국어)
- **key_strength**: 주요 강점 (한국어)
- **main_concern**: 주요 우려 사항 (한국어, 없으면 빈 문자열)"""


class ScoringAgent(BaseAgent[ScoringInput, ScoringOutput]):
    """실용성 평가 에이전트 (LLM)."""

    name = "scoring"
    uses_llm = True

    def __init__(self):
        self.settings = get_settings()

    async def run(self, input: ScoringInput) -> ScoringOutput:
        """Extraction + Delta 결과로 스코어링.

        Args:
            input: 스코어링 입력 (extraction, delta)

        Returns:
            스코어링 결과
        """
        model = self.settings.agent_models.get("scoring", "gpt-4o-mini")
        llm = get_llm_client(provider="openai", model=model)

        extraction = input.extraction
        delta = input.delta

        # Delta 텍스트 준비
        deltas_text = "\n".join(
            f"- [{d.axis}] {d.old_approach} → {d.new_approach}"
            for d in delta.core_deltas
        )

        # Evidence 커버리지 계산
        evidence_coverage = int(extraction.evidence_coverage * 100)

        prompt = SCORING_PROMPT_TEMPLATE.format(
            title=extraction.title,
            arxiv_id=extraction.arxiv_id,
            one_line_takeaway=delta.one_line_takeaway,
            problem_statement=extraction.problem_definition.statement,
            deltas_text=deltas_text,
            evidence_coverage=evidence_coverage,
            claims_count=extraction.total_claims,
        )

        try:
            result = await llm.generate_structured(
                prompt=prompt,
                output_schema=ScoringOutput,
                system_prompt=SCORING_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=2000,
            )

            return result

        except Exception as e:
            # 실패 시 기본값 반환
            return self._create_fallback_output(extraction.arxiv_id, str(e))

    def _create_fallback_output(self, arxiv_id: str, error: str) -> ScoringOutput:
        """실패 시 폴백 출력 생성."""
        return ScoringOutput(
            arxiv_id=arxiv_id,
            practicality=0,
            codeability=0,
            signal=0,
            recommendation="skip",
            reasoning=f"스코어링 실패: {error}",
            key_strength="평가 불가",
            main_concern=error,
        )
