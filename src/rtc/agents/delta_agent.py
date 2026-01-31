"""DeltaAgent - 구조적 차이 분석 (LLM)."""

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.delta_v2 import CoreDelta, DeltaOutput, TradeoffWithEvidence
from rtc.schemas.extraction_v2 import Evidence, ExtractionOutput

DELTA_SYSTEM_PROMPT = """You are a Research Agent explaining research DELTAS (not summaries).

## 목적 (중요!)
이 분석의 목적은 논문을 깊이 리뷰하는 것이 아닙니다.
"최근 연구 트렌드가 어떤 방향으로 가고 있는지"를 감지하기 위한 데일리 리포트입니다.
따라서 과장 없이 정확하게 핵심 변화만 기술합니다.

## 출력 언어 규칙 (중요!)
- 모든 출력은 반드시 한국어로 작성해야 합니다
- axis 필드도 한국어로 작성 (예: "decoding_strategy" → "디코딩 전략")
- old_approach, new_approach, why_better 모두 한국어로 작성
- 고유명사(모델명, 알고리즘명)만 영어 유지
- 영어 전문 용어는 한국어(영어) 형태로 병기

## 정확성 가이드 (반드시 지킬 것)

### 과장 표현 금지
다음과 같은 단정적 표현을 사용하지 않습니다:
- "해결했다", "자동화했다", "보장한다", "최초다"
대신 아래와 같은 완화된 표현을 사용합니다:
- "~을 제안한다"
- "~을 개선한다"
- "~을 지원한다"
- "논문에서는 ~라고 주장한다"
- "~을 목표로 한다"

### 확장 해석 금지
논문이 직접 언급하지 않은 상위 해석을 추가하지 않습니다:
- 자율 에이전트 전체 문제로 일반화
- 과학적 발견의 완전 자동화
- 모델 구조 변경이 없는 논문에서 새로운 모듈 도입이라고 표현
반드시 논문에서 명시적으로 언급한 범위까지만 기술합니다.

## CRITICAL RULES
1. Delta = STRUCTURAL CHANGE, not restatement
2. Focus on "what changed" and "why it's better"
3. Every delta needs concrete evidence
4. Be specific about axes of change
5. **ACCURACY IS PARAMOUNT**: Only describe deltas that are explicitly supported by the extraction data

## PAPER TYPES - ADAPT YOUR APPROACH
논문 유형에 따라 다른 접근이 필요합니다:

### Type A: 기존 방법 개선형
- 명확한 baseline이 있고, 그것을 직접 개선
- old_approach에 구체적인 기존 방법 기술
- 예: "이 논문은 [기존 방법 X]의 [한계 A]를 [변화 B]를 통해 개선한다"

### Type B: 새로운 문제/영역 개척형 (시스템/프레임워크 논문 포함)
- 기존에 해당 문제를 다룬 방법이 없거나, 첫 번째 시도
- old_approach를 "해당 영역의 일반적 접근" 또는 "기존에 특화된 해결책 없음"으로 기술
- 예: "이 논문은 [새로운 문제 X]에 대해 [접근법 A]를 제안한다"
- 주의: "과학적 발견을 자동화한다" 같은 확대 해석 금지
- 권장: "연구 아이디어 구체화와 서사 생성을 구조적으로 지원"

### Type C: 파운데이션 모델/테크니컬 리포트
- 데이터 설계, instruction tuning 및 학습 전략에 초점
- 새로운 추론 모듈이 있다고 서술하지 않음
- "최초"라는 표현은 "논문에서 최초라고 주장한다" 형태로 작성
- 하이퍼파라미터 상세 나열 금지

### Type D: 방법론 논문
- 문제 정의 → 기존 한계 → 제안 방법 → 트레이드오프 순서 유지
- decoding, training, sampling 개념을 혼동하지 않음
- 이 유형은 다른 논문보다 설명이 약간 자세해도 무방

## DELTA TEMPLATE (한국어로 작성)
For each delta, explain:
- axis: 어떤 차원이 변했는가? (예: "제어 패러다임", "메모리 구조", "추론 전략")
- old_approach: 기존 접근법은 무엇이었는가? (baseline이 없으면 "일반적인 기존 접근" 또는 "해당 없음"으로 표시)
- new_approach: 새로운 접근법은 무엇인가?
- why_better: 왜 이 변화가 유익한가?

## FORBIDDEN
- Problem restatement ("existing methods have low accuracy")
- Generic improvements ("our method is better")
- Vague descriptions
- 영어로 작성된 설명 (고유명사 제외)
- **허위 baseline 생성**: extraction에서 baseline이 비어있으면 fabricate하지 말 것
- **잘못된 인과관계**: "X를 개선했다"고 할 때 X가 실제 baseline인지 확인
- **과장된 표현**: "해결했다", "자동화했다", "보장한다" 등 단정적 표현 금지
- **확장 해석**: 논문 범위를 벗어난 일반화

## GOOD DELTA EXAMPLES (한국어)
- axis: "제어 패러다임", old: "탐지기 중심의 단일 판단", new: "정책 규칙 기반 분리 판단", why: "유해성 기준을 명시적으로 분리하여 해석 가능성 향상을 목표로 함"
- axis: "처리 방식", old: "토큰 단위 순차 처리", new: "청크 단위 병렬 처리", why: "지연 시간 감소 및 처리량 증가를 제안함"
- axis: "사이버보안 추론", old: "해당 영역에 특화된 오픈소스 추론 모델 없음", new: "SFT와 RLVR을 통한 사이버보안 특화 추론 모델", why: "논문에서는 최초의 오픈소스 사이버보안 추론 모델이라고 주장함"

## BAD DELTA EXAMPLES (DO NOT DO THIS)
- "기존 방법은 정밀도가 낮다" (문제점 반복)
- "성능이 향상되었다" (결과 재진술)
- "The existing approach..." (영어 사용)
- "[존재하지 않는 모델]의 한계를 개선했다" (허위 baseline)
- "과학적 발견을 자동화한다" (확장 해석)
- "혁신적인 프레임워크를 제안했다" (과장 표현)"""

DELTA_PROMPT_TEMPLATE = """Analyze the structural deltas of this paper compared to baselines.

**Paper**: {title} ({arxiv_id})

**Extraction Summary**:
Problem: {problem_statement}
Baselines: {baselines}
Method Components: {method_components}

## STEP 1: 논문 유형 판단
먼저 이 논문이 어떤 유형인지 판단하세요:
- Type A (기존 방법 개선): baselines에 구체적인 방법이 있고 직접 비교 실험이 있는 경우
- Type B (새로운 영역 개척): baselines가 비어있거나 "직접 비교 실험 없음"인 경우
- Type C (시스템/프레임워크 제안): 여러 기존 방법을 통합하는 시스템인 경우
- Type D (파운데이션 모델/테크니컬 리포트): 데이터 설계, 학습 전략 중심인 경우

## STEP 2: 유형에 맞는 one_line_takeaway 작성 (과장 표현 금지!)
- Type A: "이 논문은 [기존 방법 X]의 [구조적 한계 A]를 [핵심 변화 B]를 통해 개선한다"
- Type B: "이 논문은 [문제 영역 X]에 대해 [접근법 A]를 제안한다"
- Type C: "이 논문은 [기존의 분산된 접근들]을 통합 프레임워크로 체계화하여 [목표 A]를 지원한다"
- Type D: "이 논문은 [영역 X]에서 [학습 전략 A]를 통해 [모델 B]를 학습한다 (논문에서는 최초라고 주장함)"

## 과장 표현 금지 - 다음 표현들을 사용하지 마세요:
- "해결했다" → "개선한다" 또는 "목표로 한다"
- "자동화했다" → "지원한다" 또는 "제안한다"
- "최초다" → "논문에서는 최초라고 주장한다"
- "보장한다" → "목표로 한다" 또는 "제안한다"

Provide:
1. **one_line_takeaway**: 위 유형에 맞는 한 줄 요약 (정확성이 가장 중요! 과장 금지!)
2. **core_deltas**: 최소 1-3개의 핵심 구조적 변화
   - baselines가 없으면 old_approach를 "일반적인 기존 접근" 또는 "해당 영역에 특화된 방법 없음"으로 작성
3. **tradeoffs**: 이 접근법의 트레이드오프
4. **when_to_use**: 언제 이 방법을 사용해야 하는지
5. **when_not_to_use**: 언제 사용하지 말아야 하는지

**주의사항**:
- baselines 정보가 없거나 비어있으면 허위 baseline을 만들지 마세요
- 논문의 실제 기여를 정확히 기술하세요
- 논문 범위를 벗어난 확장 해석을 하지 마세요

한국어로 작성하되, 전문 용어는 영어를 병기하세요."""


class DeltaAgent(BaseAgent[ExtractionOutput, DeltaOutput]):
    """구조적 차이 분석 에이전트 (LLM)."""

    name = "delta"
    uses_llm = True

    def __init__(self):
        self.settings = get_settings()

    async def run(self, extraction: ExtractionOutput) -> DeltaOutput:
        """Extraction 결과로부터 Delta 분석.

        Args:
            extraction: 추출된 정보

        Returns:
            Delta 분석 결과
        """
        model = self.settings.agent_models.get("delta", "gpt-4o")
        llm = get_llm_client(provider="openai", model=model)

        # 프롬프트 준비
        baselines_text = "\n".join(
            f"- {b.name}: {b.description} (한계: {b.limitation})"
            for b in extraction.baselines
        ) or "명시된 베이스라인 없음"

        method_text = "\n".join(
            f"- {m.name}: {m.description}"
            for m in extraction.method_components
        ) or "명시된 방법론 구성 요소 없음"

        prompt = DELTA_PROMPT_TEMPLATE.format(
            title=extraction.title,
            arxiv_id=extraction.arxiv_id,
            problem_statement=extraction.problem_definition.statement,
            baselines=baselines_text,
            method_components=method_text,
        )

        try:
            result = await llm.generate_structured(
                prompt=prompt,
                output_schema=DeltaOutput,
                system_prompt=DELTA_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=4000,
            )

            return result

        except Exception as e:
            # 실패 시 기본값 반환
            return self._create_fallback_output(extraction, str(e))

    def _create_fallback_output(
        self, extraction: ExtractionOutput, error: str
    ) -> DeltaOutput:
        """실패 시 폴백 출력 생성."""
        return DeltaOutput(
            arxiv_id=extraction.arxiv_id,
            one_line_takeaway=f"[Delta 분석 실패] {extraction.title}",
            core_deltas=[
                CoreDelta(
                    axis="unknown",
                    old_approach="분석 실패",
                    new_approach="분석 실패",
                    why_better=f"오류: {error}",
                    evidence=Evidence(
                        page=None,
                        section=None,
                        quote="분석 중 오류 발생",
                        type="quote",
                    ),
                )
            ],
            tradeoffs=[],
            when_to_use="분석 실패로 판단 불가",
            when_not_to_use="분석 실패로 판단 불가",
        )
