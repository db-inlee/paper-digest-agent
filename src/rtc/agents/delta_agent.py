"""DeltaAgent - 구조적 차이 분석 (LLM)."""

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.delta_v2 import CoreDelta, DeltaOutput, TradeoffWithEvidence
from rtc.schemas.extraction_v2 import Evidence, ExtractionOutput

# Matches the limit used by verification and correction. Delta only needs enough of the
# paper to quote from; its output budget is half of extraction's, so extraction's 80k is
# more than this step can use.
FULL_TEXT_CHAR_LIMIT = 50000

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
5. **ACCURACY IS PARAMOUNT**: Only describe deltas that are explicitly supported by the
   extraction summary **or the paper's full text** provided below

## EVIDENCE RULES (반드시 지킬 것)
- `evidence.quote` 는 **논문 원문에서 그대로 복사한 문장**이어야 합니다 (verbatim).
  원문이 영어면 영어 그대로 붙여넣으세요 - 번역하지 마세요.
- **Extraction Summary 의 한국어 문장을 evidence 로 재사용하지 마세요.** 그것은 우리가
  생성한 요약이지 논문의 문장이 아닙니다.
- 가능하면 `section` 과 `page` 도 원문 기준으로 채우세요.
- **원문(Full Text)이 제공되지 않은 경우 evidence 의 quote 를 비워 두세요**
  (`quote: null`). 인용할 원문이 없는데 지어내면 안 됩니다.

## PAPER TYPES - ADAPT YOUR APPROACH
논문 유형에 따라 다른 접근이 필요합니다:

### Type A: 기존 방법 개선형
- 명확한 baseline이 있고, 그것을 직접 개선
- old_approach에 구체적인 기존 방법 기술
- 예: "이 논문은 [기존 방법 X]의 [한계 A]를 [변화 B]를 통해 개선한다"

### Type B: 새로운 문제/영역 개척형 (시스템/프레임워크 논문 포함)
- 기존에 해당 문제를 다룬 방법이 없거나, 첫 번째 시도
- old_approach 에도 **논문이 실제로 대비하는 대상**을 구체적으로 씁니다.
  직접 비교 실험이 없어도 논문은 거의 항상 무언가와 대비합니다 -
  기존 관행, 인접 분야의 방법, 사람이 수작업으로 하던 절차 등.
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
- old_approach: 논문이 대비하는 기존 접근은 무엇인가? 가능한 한 **이름으로** 지목하세요
  (예: "Fixed-env GRPO", "ReAct 스타일 단일 루프"). 근거는 baselines, baseline_methods,
  벤치마크 표의 비교 대상 이름, 문제 정의의 구조적 한계, 원문 서술 순으로 찾습니다.
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
- axis: "사이버보안 추론", old: "범용 추론 모델(GPT-4 계열)을 도메인 조정 없이 그대로 적용", new: "SFT와 RLVR을 통한 사이버보안 특화 추론 모델", why: "논문에서는 최초의 오픈소스 사이버보안 추론 모델이라고 주장함"

## BAD DELTA EXAMPLES (DO NOT DO THIS)
- "해당 영역에 특화된 방법 없음" / "해당 없음" / "일반적인 기존 접근" (내용이 없는 상투구)
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
Structural limitation of prior work: {structural_limitation}
Baselines (직접 비교 실험 대상): {baselines}
Baseline methods mentioned in the paper: {baseline_methods}
Benchmark comparison targets (결과 표의 비교 대상 이름): {benchmark_baseline_keys}
Method Components: {method_components}

**Paper Full Text** (evidence 를 여기서 verbatim 인용하세요):
{full_text}

## STEP 0: 대비 대상 확인
old_approach 에 쓸 대상을 아래 순서로 찾으세요:
1. Baselines 의 이름
2. Baseline methods 의 이름
3. Benchmark comparison targets 의 키 이름
4. Structural limitation 이 지목하는 기존 방식
5. 원문에서 논문이 "unlike X", "prior work", "conventional" 로 대비하는 대상
위 다섯에서 아무것도 못 찾은 경우에만, 대비 대상이 확인되지 않는다는 사실을
이 논문에 맞는 표현으로 한 번 서술합니다. 정해진 문구를 붙여넣지 마세요.

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
2. **core_deltas**: 2-5개의 핵심 구조적 변화 (방법론 구성 요소가 많으면 더 많은 delta 추출)
   - old_approach 는 위 STEP 0 에서 확인한 대비 대상을 근거로 구체적으로 작성합니다
   - 정말로 대비 대상을 찾을 수 없으면 그 사실을 한 문장으로 짧게 쓰되,
     정해진 문구를 반복하지 말고 이 논문에 맞게 서술하세요
   - 각 delta 의 evidence.quote 는 원문에서 그대로 인용합니다 (원문이 없으면 비웁니다)
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

    async def run(
        self,
        extraction: ExtractionOutput,
        full_text: str | None = None,
    ) -> DeltaOutput:
        """Extraction 결과로부터 Delta 분석.

        Args:
            extraction: 추출된 정보
            full_text: 논문 원문. evidence 를 원문에서 인용하기 위해 필요하며,
                없으면 프롬프트가 evidence 를 비우도록 지시한다.

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

        baseline_methods_text = ", ".join(
            extraction.problem_definition.baseline_methods
        ) or "명시된 기존 방법명 없음"

        # 결과 표의 비교 대상 이름. baselines[] 가 비어도 여기에 실명이 남아 있는
        # 경우가 있어 old_approach 의 근거로 쓴다.
        benchmark_keys: list[str] = []
        for bench in extraction.all_benchmarks:
            for key in bench.baseline_results:
                if key not in benchmark_keys:
                    benchmark_keys.append(key)
        benchmark_keys_text = ", ".join(benchmark_keys) or "결과 표에 비교 대상 없음"

        method_parts = []
        for m in extraction.method_components:
            part = f"- {m.name}: {m.description}"
            if m.inputs:
                part += f"\n  입력: {', '.join(m.inputs)}"
            if m.outputs:
                part += f"\n  출력: {', '.join(m.outputs)}"
            if m.implementation_hint:
                part += f"\n  구현 힌트: {m.implementation_hint}"
            if m.role:
                part += f"\n  역할: {m.role}"
            method_parts.append(part)
        method_text = "\n".join(method_parts) or "명시된 방법론 구성 요소 없음"

        if full_text:
            paper_text = full_text[:FULL_TEXT_CHAR_LIMIT]
            if len(full_text) > FULL_TEXT_CHAR_LIMIT:
                paper_text += "\n... (truncated)"
        else:
            paper_text = (
                "(원문이 제공되지 않았습니다. evidence 의 quote 를 비워 두세요 - "
                "Extraction Summary 의 문장을 인용으로 쓰면 안 됩니다.)"
            )

        prompt = DELTA_PROMPT_TEMPLATE.format(
            title=extraction.title,
            arxiv_id=extraction.arxiv_id,
            problem_statement=extraction.problem_definition.statement,
            structural_limitation=(
                extraction.problem_definition.structural_limitation or "명시되지 않음"
            ),
            baselines=baselines_text,
            baseline_methods=baseline_methods_text,
            benchmark_baseline_keys=benchmark_keys_text,
            method_components=method_text,
            full_text=paper_text,
        )

        try:
            result = await llm.generate_structured(
                prompt=prompt,
                output_schema=DeltaOutput,
                system_prompt=DELTA_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=6000,
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
