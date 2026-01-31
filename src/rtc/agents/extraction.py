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

## 목적 (중요!)
이 추출의 목적은 논문을 깊이 리뷰하거나 재현하는 것이 아닙니다.
하루에 약 3편의 논문을 빠르게 훑으며 "최근 연구 트렌드가 어떤 방향으로 가고 있는지"를 감지하는 것이 목적입니다.
따라서 코드 디테일, 하이퍼파라미터, 구현 세부사항은 최소화합니다.

## 출력 언어 규칙 (중요!)
- 모든 출력은 반드시 한국어로 작성해야 합니다
- 고유명사(모델명, 알고리즘명, 데이터셋명)만 영어 유지
- 영어 전문 용어는 한국어(영어) 형태로 병기
- 예시:
  - "Cross-modal hallucinations" → "크로스 모달 환각(cross-modal hallucinations)"
  - "The paper addresses..." → "이 논문은 ...를 다룹니다"
  - "attention mechanism" → "어텐션 메커니즘(attention mechanism)"

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
반드시 논문에서 명시적으로 언급한 범위까지만 요약합니다.

## CRITICAL RULES
1. Evidence-first: Every claim needs (Evidence: p.X §Y) pointer
2. **STRICTLY NO SPECULATION**: Only extract facts that are **explicitly stated** in the paper with direct quotes
3. Structural focus: Extract implementation-relevant information
4. Be concise - 데일리 리포트용이므로 핵심만 추출
5. **Distinguish between direct baselines vs general related work**: Only list methods as baselines if the paper **directly compares** against them with experiments/metrics

## ABSOLUTELY FORBIDDEN
- Claims without evidence
- **Speculation, inference, or filling in gaps** - if not stated, leave it empty or say "명시되지 않음"
- Restating the abstract
- Generic descriptions
- 영어로 작성된 설명 (고유명사 제외)
- **Inventing baselines**: If no direct comparison exists, do NOT fabricate one
- **Misrepresenting paper's contribution**: If this is the first model of its kind, say so clearly
- **Confusing related work with baselines**: Related work mentioned for context ≠ baseline being improved upon
- **하이퍼파라미터 상세 나열**: 데일리 리포트에는 불필요
- **논문에 없는 코드 구조나 함수 이름 만들어 설명**

## BASELINE EXTRACTION RULES
Only include as "baseline" if:
1. The paper explicitly runs experiments comparing against it
2. The paper claims to directly improve upon it with measurable metrics
3. There is a clear before/after comparison

Do NOT include as "baseline":
- Related work mentioned for background context
- Prior work by same authors that shares code/architecture but isn't being "fixed"
- General category of methods (e.g., "instruction-following models") without specific named methods

## 논문 유형 판별 (중요!)
### 시스템/프레임워크 논문
- 초점: 오프라인/온라인 분리, 재사용 가능한 패턴, 구조화, 효율성 개선
- 주의: "과학적 발견을 자동화한다", "자율 연구 에이전트 혁신" 같은 확대 해석 금지
- 권장 표현: "연구 아이디어 구체화와 서사 생성을 구조적으로 지원"

### 파운데이션 모델/테크니컬 리포트
- 초점: 데이터 설계, instruction tuning 및 학습 전략
- 주의: 새로운 추론 모듈이 있다고 서술하지 않음, 하이퍼파라미터 상세 나열 금지
- "최초"라는 표현은 반드시 "논문에서 최초라고 주장한다" 형태로 작성

### 방법론 논문
- 문제 정의 → 기존 한계 → 제안 방법 → 트레이드오프 순서 유지
- decoding, training, sampling 개념을 혼동하지 않음
- 이 유형은 다른 논문보다 설명이 약간 자세해도 무방

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

Extract:
1. **Problem Definition**: What problem does this paper solve?
   - What is the core problem being addressed?
   - Is this improving existing methods, OR introducing a new approach to an unsolved problem?
   - If improving existing methods, what specific structural limitation is being addressed? (must have direct quote)
   - If this is the first of its kind, state that clearly: "기존에 이 문제를 다룬 방법이 없거나, 최초의 시도임"

2. **Baselines**: ONLY list methods that are **directly compared in experiments**
   - A baseline must have experimental results compared against the proposed method
   - Do NOT include methods merely mentioned in Related Work section
   - If no direct experimental comparisons exist, leave this empty or write "직접 비교 실험 없음"
   - For each baseline: name, brief description, and **specific limitation that experiments demonstrate**

3. **Method Components**: What are the key components of the proposed method? (inputs, outputs, implementation hints)

4. **Benchmark**: What datasets/metrics are used? What are the results?

5. **Claims**: What are the main claims? (method, result, comparison, limitation)

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
            content = input.full_text[:50000]  # 토큰 제한
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
                max_tokens=8000,
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
            benchmark=None,
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
