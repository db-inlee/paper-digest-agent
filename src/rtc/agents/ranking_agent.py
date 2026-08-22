"""RankingAgent - 후보 전체를 한 컨텍스트에 넣어 상대 순위 산출 (LLM, 1회 호출)."""

import random
from dataclasses import dataclass, field
from typing import Optional

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.llm import get_llm_client
from rtc.schemas import PaperCandidate
from rtc.schemas.ranking import RankedPaper, RankingOutput, RankingResult
from rtc.schemas.skim import SkimSummary

# 현행 skim과 동일한 절단 상한 (agents/skim.py)
ABSTRACT_CHAR_LIMIT = 1500

RANKING_SYSTEM_PROMPT = """You rank today's candidate papers RELATIVE TO EACH OTHER
to decide which deserve deep analysis.

## AXES (relative, never absolute)
1. Delta novelty - does the abstract signal a structural departure from prior work,
   or a recombination of known parts? Look for explicit contrast sentences
   ("unlike prior work", "existing methods suffer from", ...).
2. Problem importance - is the problem a bottleneck for the field, or a narrow case?

Evidence strength is NOT an axis: at this stage only the abstract is available,
and the deep pipeline's verification stage already covers it.

## CRITICAL RULES
1. This is a RANKING, not scoring. Every paper gets a distinct rank, 1 = best.
2. IGNORE the order in which papers are listed. Position carries no information.
3. Every reason must cite something SPECIFIC to that paper. Never reuse a phrase
   across papers. Generic reasons ("novel approach", "practical contribution")
   are failures.
4. Reasons in Korean, 1-2 sentences. For the top {top_n} explain why the paper was
   selected; for the rest explain in one line why it lost to the papers above it."""

RANKING_PROMPT_TEMPLATE = """Rank ALL {n} candidate papers below.

{papers_text}

Return every paper exactly once, with a distinct rank from 1 to {n}."""


@dataclass
class RankingInput:
    """RankingAgent 입력."""

    run_date: str  # YYYY-MM-DD - 셔플 시드로도 쓰임
    papers: list[SkimSummary]  # 카테고리·임계 통과한 후보 풀
    candidates: list[PaperCandidate] = field(default_factory=list)  # abstract 출처
    top_n: int = 3  # 선정 이유를 요구할 상위 개수


class RankingAgent(BaseAgent[RankingInput, RankingResult]):
    """후보 전체 1회 호출로 상대 순위를 매기는 에이전트 (LLM).

    절대 점수가 동점으로 수렴하는 문제를 상대 비교로 우회합니다. 실패하면
    빈 결과에 ``method="fallback"``을 실어 반환하고, 호출자가 기존 선별을
    유지합니다 - 순위 버그가 파이프라인을 멈추게 하지 않습니다.
    """

    name = "ranking"
    uses_llm = True

    def __init__(self):
        self.settings = get_settings()

    async def run(self, input: RankingInput) -> RankingResult:
        """후보 순위 산출.

        Args:
            input: 후보 풀과 실행 날짜

        Returns:
            순위 결과. 실패 시 ``method="fallback"``.
        """
        papers = input.papers
        if len(papers) < 2:
            return RankingResult(method="fallback", error="Fewer than two candidates")

        ordered = self._shuffle(papers, input.run_date)
        papers_text = self._format_papers(ordered, input.candidates)

        model = self.settings.agent_models.get("ranking", "gpt-4o-mini")
        llm = get_llm_client(provider="openai", model=model)

        try:
            output = await llm.generate_structured(
                prompt=RANKING_PROMPT_TEMPLATE.format(
                    n=len(ordered), papers_text=papers_text
                ),
                output_schema=RankingOutput,
                system_prompt=RANKING_SYSTEM_PROMPT.format(top_n=input.top_n),
                temperature=0.0,
                max_tokens=2000,
            )
        except Exception as e:
            return RankingResult(method="fallback", error=f"LLM call failed: {e}")

        problem = self._sanity_error(output.ranked, papers)
        if problem:
            return RankingResult(method="fallback", error=problem)

        return RankingResult(ranked=output.ranked, method="llm")

    @staticmethod
    def _shuffle(papers: list[SkimSummary], run_date: str) -> list[SkimSummary]:
        """Order the prompt by a date-seeded shuffle.

        Any fixed order correlates the model's position bias with whatever the
        order encodes; arxiv_id order in particular would reproduce exactly the
        bias this agent exists to remove. The seed keeps a run reproducible.
        """
        ordered = list(papers)
        random.Random(run_date).shuffle(ordered)
        return ordered

    def _format_papers(
        self, papers: list[SkimSummary], candidates: list[PaperCandidate]
    ) -> str:
        """프롬프트용 후보 텍스트. abstract는 arxiv_id로 조인."""
        abstracts = {c.arxiv_id: c.abstract for c in candidates}

        parts = []
        for i, paper in enumerate(papers, 1):
            abstract = (abstracts.get(paper.arxiv_id) or "")[:ABSTRACT_CHAR_LIMIT]
            parts.append(
                f"--- Candidate {i} ---\n"
                f"ArXiv ID: {paper.arxiv_id}\n"
                f"Title: {paper.title}\n"
                f"Category: {paper.category} | "
                f"Matched keywords: {', '.join(paper.matched_keywords)}\n"
                f"Tags: {', '.join(paper.tags)}\n"
                f"Abstract: {abstract}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _sanity_error(
        ranked: list[RankedPaper], papers: list[SkimSummary]
    ) -> Optional[str]:
        """Reject a ranking the schema alone cannot rule out.

        JSON mode does not enforce set membership or rank uniqueness, so a
        dropped, duplicated or hallucinated paper has to be caught here.

        Returns:
            문제 설명. 건전하면 None.
        """
        expected = {p.arxiv_id for p in papers}
        got = {r.arxiv_id for r in ranked}

        if got != expected:
            missing = sorted(expected - got)
            unknown = sorted(got - expected)
            return f"Paper set mismatch (missing={missing}, unknown={unknown})"

        if len(ranked) != len(expected):
            return f"Duplicate entries ({len(ranked)} rows for {len(expected)} papers)"

        ranks = sorted(r.rank for r in ranked)
        if ranks != list(range(1, len(expected) + 1)):
            return f"Ranks are not 1..{len(expected)} without gaps: {ranks}"

        return None
