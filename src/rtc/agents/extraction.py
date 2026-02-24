"""ExtractionAgent - 구조화된 정보 추출 (LLM)."""

from dataclasses import dataclass
from typing import Optional

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.schemas.parsed import ParsedPDF
from rtc.schemas.skim import SkimSummary


@dataclass
class ExtractionInput:
    """Extraction 입력."""

    arxiv_id: str
    title: str
    abstract: str
    full_text: Optional[str] = None  # PDF 파싱 결과
    skim_summary: Optional[SkimSummary] = None


EXTRACTION_SYSTEM_PROMPT = """You are a Research Agent extracting structured information from papers.

## 목적
논문의 핵심 구조와 기여를 정확하고 상세하게 추출합니다.
각 방법론 구성 요소를 개별적으로 분리하여 아키텍처의 전체 그림을 파악할 수 있도록 합니다.

## 출력 언어 규칙 (중요!)
- 모든 출력은 반드시 한국어로 작성해야 합니다
- 고유명사(모델명, 알고리즘명, 데이터셋명)만 영어 유지
- 영어 전문 용어는 한국어(영어) 형태로 병기
- 예시:
  - "Cross-modal hallucinations" → "크로스 모달 환각(cross-modal hallucinations)"
  - "attention mechanism" → "어텐션 메커니즘(attention mechanism)"

## 정확성 가이드 (반드시 지킬 것)

### 과장 표현 금지
다음과 같은 단정적 표현을 사용하지 않습니다:
- "해결했다", "자동화했다", "보장한다", "최초다"
대신 아래와 같은 완화된 표현을 사용합니다:
- "~을 제안한다", "~을 개선한다", "~을 지원한다"
- "논문에서는 ~라고 주장한다", "~을 목표로 한다"

### 확장 해석 금지
논문이 직접 언급하지 않은 상위 해석을 추가하지 않습니다.
반드시 논문에서 명시적으로 언급한 범위까지만 요약합니다.

## CRITICAL RULES
1. Evidence-first: Every claim needs (Evidence: p.X §Y) pointer
2. **STRICTLY NO SPECULATION**: Only extract facts that are **explicitly stated** in the paper
3. **DETAILED METHOD DECOMPOSITION**: 논문의 방법론을 개별 구성 요소로 세밀하게 분해
4. **Distinguish between direct baselines vs general related work**: Only list methods as baselines if the paper **directly compares** against them

## ABSOLUTELY FORBIDDEN
- Claims without evidence
- **Speculation, inference, or filling in gaps** - if not stated, leave it empty or say "명시되지 않음"
- Restating the abstract
- Generic descriptions
- 영어로 작성된 설명 (고유명사 제외)
- **Inventing baselines**: If no direct comparison exists, do NOT fabricate one
- **논문에 없는 코드 구조나 함수 이름 만들어 설명**
- **방법론 구성 요소를 하나로 뭉치기**: 각 구성 요소를 반드시 별도 항목으로 분리

## BASELINE EXTRACTION RULES
Only include as "baseline" if:
1. The paper explicitly runs experiments comparing against it
2. The paper claims to directly improve upon it with measurable metrics
3. There is a clear before/after comparison

Do NOT include as "baseline":
- Related work mentioned for background context
- General category of methods without specific named methods

## OUTPUT REQUIREMENTS
For each claim/statement, you MUST provide evidence:
- page number (if available)
- section name
- direct quote (brief)"""

EXTRACTION_PROMPT_TEMPLATE = """Extract structured information from this paper.

**Title**: {title}
**ArXiv ID**: {arxiv_id}

**Content**:
{content}

Extract the following with maximum detail:

1. **Problem Definition**: What problem does this paper solve?
   - What is the core problem being addressed?
   - Is this improving existing methods, OR introducing a new approach to an unsolved problem?
   - If improving existing methods, what specific structural limitation is being addressed? (must have direct quote)
   - If this is the first of its kind, state that clearly

2. **Baselines**: ONLY list methods that are **directly compared in experiments**
   - A baseline must have experimental results compared against the proposed method
   - Do NOT include methods merely mentioned in Related Work section
   - If no direct experimental comparisons exist, leave this empty
   - For each baseline: name, brief description, and **specific limitation that experiments demonstrate**

3. **Method Components** (매우 중요! 세밀하게 분해할 것):
   각 아키텍처 구성 요소, 알고리즘 모듈, 학습 기법을 **개별 항목으로 반드시 분리**하세요.

   분해 원칙:
   - 독립적으로 설명 가능한 모듈은 각각 별도 항목으로 추출
   - 하위 구성 요소도 별도로 분리 (예: Transformer → Multi-Head Attention, Positional Encoding, FFN 등)
   - 최소 3개 이상의 구성 요소를 추출해야 합니다
   - 각 구성 요소에 대해: 이름, 상세 설명, 입력, 출력, 구현 힌트를 모두 기술

   예시 (Transformer 논문의 경우):
   - Scaled Dot-Product Attention: Q, K, V의 내적 기반 어텐션 계산
   - Multi-Head Attention: 여러 어텐션 헤드를 병렬로 실행하여 다양한 표현 부분공간 학습
   - Position-wise Feed-Forward Network: 각 위치에 독립적으로 적용되는 2층 FFN
   - Positional Encoding: 위치 정보를 사인/코사인 함수로 인코딩
   - Encoder Block: Multi-Head Attention + FFN + Residual Connection + Layer Norm
   - Decoder Block: Masked Self-Attention + Cross-Attention + FFN
   - Label Smoothing: 정규화를 위한 라벨 스무딩 기법

4. **Benchmarks**: 사용된 모든 데이터셋/평가 지표를 각각 별도로 기록
   - 여러 벤치마크가 있으면 모두 추출 (리스트 형태)
   - 각 벤치마크별: 데이터셋명, 평가 지표, 베이스라인 결과, 제안 방법 결과

5. **Claims**: 논문의 주요 주장을 최소 5개 이상 추출
   - method: 방법론적 기여
   - result: 실험 결과
   - comparison: 기존 방법 대비 비교
   - limitation: 한계점
   - architecture: 구조적 설계 선택
   - efficiency: 효율성 관련 주장
   - ablation: 에블레이션 결과

IMPORTANT: For EACH item, provide evidence (page, section, **exact quote from paper**).
If information is not explicitly stated, write "논문에 명시되지 않음" - do NOT speculate.

한국어로 작성하되, 전문 용어는 영어를 병기하세요."""


class ExtractionAgent(BaseAgent[ExtractionInput, ExtractionOutput]):
    """구조화된 정보 추출 에이전트 (LLM)."""

    name = "extraction"
    uses_llm = True

    def __init__(self):
        self.settings = get_settings()

    async def run(self, input: ExtractionInput) -> ExtractionOutput:
        """논문에서 구조화된 정보 추출.

        Args:
            input: 추출 입력 (논문 정보)

        Returns:
            추출된 구조화 정보
        """
        model = self.settings.agent_models.get("extraction", "gpt-4o")
        llm = get_llm_client(provider="openai", model=model)

        # 콘텐츠 준비
        if input.full_text:
            content = input.full_text[:80000]  # 토큰 제한 (확대)
            extraction_mode = "full"
        else:
            content = f"Abstract:\n{input.abstract}"
            extraction_mode = "lite"

        prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            title=input.title,
            arxiv_id=input.arxiv_id,
            content=content,
        )

        try:
            result = await llm.generate_structured(
                prompt=prompt,
                output_schema=ExtractionOutput,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=12000,
            )

            # 추출 모드 설정
            result.extraction_mode = extraction_mode

            return result

        except Exception as e:
            # 실패 시 기본값 반환
            return self._create_fallback_output(input, extraction_mode, str(e))

    def _create_fallback_output(
        self, input: ExtractionInput, mode: str, error: str
    ) -> ExtractionOutput:
        """실패 시 폴백 출력 생성."""
        from rtc.schemas.extraction_v2 import (
            ClaimWithEvidence,
            ProblemDefinition,
        )

        return ExtractionOutput(
            arxiv_id=input.arxiv_id,
            title=input.title,
            problem_definition=ProblemDefinition(
                statement=f"[추출 실패] {error}",
                baseline_methods=[],
                structural_limitation="추출 실패",
                evidence=[],
            ),
            baselines=[],
            method_components=[],
            benchmarks=[],
            claims=[
                ClaimWithEvidence(
                    claim_id="error",
                    text=f"추출 중 오류 발생: {error}",
                    claim_type="limitation",
                    confidence=0.0,
                    evidence=[],
                )
            ],
            extraction_mode=mode,
        )
