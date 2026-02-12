"""UltraSkimAgent - 빠른 논문 스킴 (LLM, 배치 처리)."""

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas import PaperCandidate
from rtc.schemas.skim import BatchSkimResult, SkimSummary

SKIM_SYSTEM_PROMPT = """You are a rapid paper skimming expert for LLM/Agent research.
Your goal is to quickly assess each paper's relevance and importance.

## CRITICAL RULES
1. Speed over depth: Extract only essential signals
2. Be concise: One-liner should be 1-2 sentences max
3. Score honestly: Don't inflate scores
4. Categorize accurately: Choose the best fitting category

## SCORING GUIDE (interest_score 1-5)
- 5: Groundbreaking work, paradigm shift, must-read
- 4: Significant contribution, novel approach, worth deep analysis
- 3: Useful contribution, incremental improvement
- 2: Minor contribution, limited novelty
- 1: Not relevant or low quality

## CATEGORIES
- agent: AI agents, tool use, function calling, multi-agent
- rag: Retrieval, RAG, knowledge retrieval
- reasoning: Chain-of-thought, planning, problem solving
- training: Fine-tuning, RLHF, instruction tuning
- evaluation: Benchmarks, metrics, evaluation methods
- other: Anything else"""

SKIM_PROMPT_TEMPLATE = """Skim the following papers and provide a brief assessment for each.

Papers to skim:
{papers_text}

For each paper, provide:
1. one_liner: 한국어로 1-2문장 요약 (핵심 기여만)
2. tags: 3-5개 키워드 태그 (영어)
3. interest_score: 1-5 점수
4. interest_reason: 점수 판단 근거 (한국어, 1문장)
5. baseline_mentioned: 주요 베이스라인 (있으면)
6. category: agent/rag/reasoning/training/evaluation/other 중 택1
7. has_code: 코드 공개 여부 (abstract에서 언급 시)"""


class UltraSkimAgent(BaseAgent[list[PaperCandidate], BatchSkimResult]):
    """배치 단위 빠른 스킴 에이전트 (LLM).

    여러 논문을 하나의 LLM 호출로 처리하여 비용을 절감합니다.
    """

    name = "ultra_skim"
    uses_llm = True

    def __init__(self, batch_size: int = 10):
        """초기화.

        Args:
            batch_size: 한 번에 처리할 논문 수
        """
        self.batch_size = batch_size
        self.settings = get_settings()

    async def run(self, papers: list[PaperCandidate]) -> BatchSkimResult:
        """논문 배치 스킴 실행.

        Args:
            papers: 스킴할 논문 목록

        Returns:
            배치 스킴 결과
        """
        if not papers:
            return BatchSkimResult(papers=[], total_processed=0)

        all_summaries: list[SkimSummary] = []
        errors: list[str] = []

        # 배치 단위로 처리
        for i in range(0, len(papers), self.batch_size):
            batch = papers[i : i + self.batch_size]

            try:
                summaries = await self._skim_batch(batch)
                all_summaries.extend(summaries)
            except Exception as e:
                errors.append(f"Batch {i // self.batch_size}: {str(e)}")
                # 실패한 배치는 기본값으로 처리
                for paper in batch:
                    all_summaries.append(self._create_default_summary(paper))

        return BatchSkimResult(
            papers=all_summaries,
            total_processed=len(papers),
            errors=errors,
        )

    async def _skim_batch(self, papers: list[PaperCandidate]) -> list[SkimSummary]:
        """단일 배치 스킴.

        Args:
            papers: 배치 내 논문들

        Returns:
            스킴 결과 목록
        """
        model = self.settings.agent_models.get("skim", "gpt-4o-mini")
        llm = get_llm_client(provider="openai", model=model)

        # 논문 텍스트 포맷팅
        papers_text = self._format_papers_for_prompt(papers)

        prompt = SKIM_PROMPT_TEMPLATE.format(papers_text=papers_text)

        # 배치 스킴 결과 스키마
        result = await llm.generate_structured(
            prompt=prompt,
            output_schema=BatchSkimOutput,
            system_prompt=SKIM_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=4000,
        )

        # 결과를 SkimSummary로 변환
        summaries = []
        for i, paper in enumerate(papers):
            if i < len(result.results):
                skim = result.results[i]
                summaries.append(
                    SkimSummary(
                        arxiv_id=paper.arxiv_id,
                        title=paper.title,
                        one_liner=skim.one_liner,
                        tags=skim.tags,
                        interest_score=skim.interest_score,
                        interest_reason=skim.interest_reason,
                        baseline_mentioned=skim.baseline_mentioned,
                        category=skim.category,
                        has_code=skim.has_code or bool(paper.github_url),
                        link=f"https://arxiv.org/abs/{paper.arxiv_id}",
                        github_url=paper.github_url,
                        github_stars=paper.github_stars,
                        matched_keywords=paper.matched_keywords,
                    )
                )
            else:
                summaries.append(self._create_default_summary(paper))

        return summaries

    def _format_papers_for_prompt(self, papers: list[PaperCandidate]) -> str:
        """프롬프트용 논문 텍스트 포맷팅."""
        parts = []
        for i, paper in enumerate(papers, 1):
            parts.append(
                f"--- Paper {i} ---\n"
                f"ArXiv ID: {paper.arxiv_id}\n"
                f"Title: {paper.title}\n"
                f"Abstract: {paper.abstract[:1500]}..."
                if len(paper.abstract) > 1500
                else f"--- Paper {i} ---\n"
                f"ArXiv ID: {paper.arxiv_id}\n"
                f"Title: {paper.title}\n"
                f"Abstract: {paper.abstract}"
            )
        return "\n\n".join(parts)

    def _create_default_summary(self, paper: PaperCandidate) -> SkimSummary:
        """기본 스킴 결과 생성 (실패 시 사용)."""
        return SkimSummary(
            arxiv_id=paper.arxiv_id,
            title=paper.title,
            one_liner="[스킴 실패] " + paper.title,
            tags=[],
            interest_score=1,
            interest_reason="스킴 처리 중 오류 발생",
            baseline_mentioned=None,
            category="other",
            has_code=bool(paper.github_url),
            link=f"https://arxiv.org/abs/{paper.arxiv_id}",
            github_url=paper.github_url,
            github_stars=paper.github_stars,
            matched_keywords=paper.matched_keywords,
        )


# LLM 출력용 내부 스키마
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SingleSkimOutput(BaseModel):
    """단일 논문 스킴 결과 (LLM 출력용)."""

    one_liner: str
    tags: list[str]
    interest_score: int = Field(..., ge=1, le=5)
    interest_reason: str
    baseline_mentioned: Optional[str] = None
    category: Literal["agent", "rag", "reasoning", "training", "evaluation", "other"]
    has_code: bool = False


class BatchSkimOutput(BaseModel):
    """배치 스킴 결과 (LLM 출력용)."""

    results: list[SingleSkimOutput]
