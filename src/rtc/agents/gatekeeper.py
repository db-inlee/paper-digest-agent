"""Gatekeeper 에이전트 - Deep 분석 대상 결정 (비-LLM)."""

from dataclasses import dataclass

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.schemas.skim import BatchSkimResult, SkimSummary


@dataclass
class GatekeeperOutput:
    """Gatekeeper 출력."""

    deep_candidates: list[str]  # Deep 분석 대상 arxiv_ids
    all_papers: list[SkimSummary]  # 전체 스킴 결과
    filtered_count: int  # 필터링된 논문 수
    reason: str  # 선택 이유


class Gatekeeper(BaseAgent[BatchSkimResult, GatekeeperOutput]):
    """Deep 분석 대상 결정 에이전트 (비-LLM).

    interest_score 기반으로 Deep 분석 대상을 선정합니다.
    """

    name = "gatekeeper"
    uses_llm = False

    # 관심 카테고리 (이 카테고리만 Deep 분석 대상)
    INTEREST_CATEGORIES = {"agent", "rag", "reasoning"}

    def __init__(
        self,
        interest_threshold: int = 4,
        max_deep_papers: int = 3,
    ):
        """초기화.

        Args:
            interest_threshold: Deep 분석 임계 점수 (이상이면 후보)
            max_deep_papers: 하루 최대 Deep 분석 수
        """
        self.interest_threshold = interest_threshold
        self.max_deep_papers = max_deep_papers
        self.settings = get_settings()

    async def run(self, skim_result: BatchSkimResult) -> GatekeeperOutput:
        """Deep 분석 대상 선정.

        Args:
            skim_result: 스킴 결과

        Returns:
            Deep 분석 대상 목록
        """
        papers = skim_result.papers

        if not papers:
            return GatekeeperOutput(
                deep_candidates=[],
                all_papers=[],
                filtered_count=0,
                reason="스킴된 논문 없음",
            )

        # 1. 관심 카테고리 필터링 (agent, rag, reasoning만)
        category_filtered = [
            p for p in papers if p.category in self.INTEREST_CATEGORIES
        ]

        # 2. interest_score 기준 필터링
        qualified = [
            p for p in category_filtered if p.interest_score >= self.interest_threshold
        ]

        # 3. interest_score 높은 순으로 정렬
        qualified.sort(key=lambda p: (-p.interest_score, p.arxiv_id))

        # 4. 최대 개수 제한
        selected = qualified[: self.max_deep_papers]
        deep_candidates = [p.arxiv_id for p in selected]

        # 선택 이유 생성
        excluded_count = len(papers) - len(category_filtered)
        if not deep_candidates:
            reason = (
                f"카테고리 필터({', '.join(self.INTEREST_CATEGORIES)}) 후 {len(category_filtered)}개, "
                f"interest_score >= {self.interest_threshold}인 논문 없음"
            )
        else:
            reason = (
                f"카테고리 필터 후 {len(category_filtered)}개 (제외: {excluded_count}개), "
                f"점수 필터 후 {len(qualified)}개 → 상위 {len(selected)}개 선택"
            )

        return GatekeeperOutput(
            deep_candidates=deep_candidates,
            all_papers=papers,
            filtered_count=len(qualified),
            reason=reason,
        )

    def get_paper_by_id(
        self, arxiv_id: str, papers: list[SkimSummary]
    ) -> SkimSummary | None:
        """arxiv_id로 논문 찾기."""
        for paper in papers:
            if paper.arxiv_id == arxiv_id:
                return paper
        return None
