"""CandidateFetcher 에이전트 - 논문 수집 (비-LLM)."""

from dataclasses import dataclass

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.mcp.servers.hf_papers_server import HFPapersServer, paper_dict_to_candidate
from rtc.schemas import PaperCandidate


@dataclass
class FetchInput:
    """Fetcher 입력."""

    run_date: str  # YYYY-MM-DD


@dataclass
class FetchOutput:
    """Fetcher 출력."""

    candidates: list[PaperCandidate]
    total_collected: int
    total_after_filter: int
    skipped_previously_processed: int
    skipped_keyword_filter: int


class CandidateFetcher(BaseAgent[FetchInput, FetchOutput]):
    """HF Papers에서 논문 수집 및 필터링 (비-LLM).

    기존 collect_node + filter_node 로직을 통합합니다.
    """

    name = "candidate_fetcher"
    uses_llm = False

    def __init__(self):
        self.settings = get_settings()

    async def run(self, input: FetchInput) -> FetchOutput:
        """논문 수집 및 필터링 실행.

        Args:
            input: 실행 날짜 정보

        Returns:
            필터링된 논문 후보 목록
        """
        # 1. HF Papers에서 수집
        candidates = await self._collect_papers()
        total_collected = len(candidates)

        # 2. 필터링 적용
        filtered, stats = self._apply_filters(candidates)

        return FetchOutput(
            candidates=filtered,
            total_collected=total_collected,
            total_after_filter=len(filtered),
            skipped_previously_processed=stats["skipped_processed"],
            skipped_keyword_filter=stats["skipped_keyword"],
        )

    async def _collect_papers(self) -> list[PaperCandidate]:
        """HF Papers에서 논문 수집."""
        server = HFPapersServer()

        try:
            paper_dicts = await server.search_papers(
                days_back=self.settings.hf_papers_lookback_days,
                min_votes=self.settings.hf_papers_min_votes,
            )
            return [paper_dict_to_candidate(p) for p in paper_dicts]
        finally:
            await server.close()

    def _apply_filters(
        self, candidates: list[PaperCandidate]
    ) -> tuple[list[PaperCandidate], dict]:
        """필터링 적용.

        Args:
            candidates: 원본 논문 목록

        Returns:
            (필터링된 목록, 통계 dict)
        """
        seen_ids: set[str] = set()
        filtered: list[PaperCandidate] = []

        # 이전에 처리된 논문 ID 로드
        processed_ids = self._load_processed_arxiv_ids()

        stats = {
            "skipped_processed": 0,
            "skipped_keyword": 0,
            "skipped_duplicate": 0,
            "skipped_hard_filter": 0,
        }

        keywords = self.settings.hf_papers_keywords

        for paper in candidates:
            base_id = paper.arxiv_id.split("v")[0]

            # 이전에 처리된 논문 건너뛰기
            if base_id in processed_ids:
                stats["skipped_processed"] += 1
                continue

            # 중복 제거
            if base_id in seen_ids:
                stats["skipped_duplicate"] += 1
                continue
            seen_ids.add(base_id)

            # 하드 필터
            if not self._passes_hard_filters(paper):
                stats["skipped_hard_filter"] += 1
                continue

            # 키워드 필터
            if keywords and not self._matches_keywords(paper, keywords):
                stats["skipped_keyword"] += 1
                continue

            filtered.append(paper)

        return filtered, stats

    def _load_processed_arxiv_ids(self) -> set[str]:
        """이전에 처리된 논문 ID 로드 (reports 폴더 기반)."""
        processed_ids: set[str] = set()

        # reports/ 폴더에서 처리된 논문 ID 추출
        reports_dir = self.settings.reports_dir
        if not reports_dir.exists():
            return processed_ids

        for paper_dir in reports_dir.iterdir():
            if paper_dir.is_dir() and paper_dir.name != "daily":
                # 폴더명에서 arxiv_id 추출 (예: 2601.20833-paper-title)
                parts = paper_dir.name.split("-")
                if parts:
                    arxiv_id = parts[0]
                    base_id = arxiv_id.split("v")[0]
                    processed_ids.add(base_id)

        return processed_ids

    def _passes_hard_filters(self, paper: PaperCandidate) -> bool:
        """하드 필터 적용."""
        # 초록 100자 이상 필수
        if not paper.abstract or len(paper.abstract) < 100:
            return False

        # 제목 필수
        if not paper.title:
            return False

        # survey/tutorial 등 제외
        title_lower = paper.title.lower()
        skip_patterns = [
            "survey",
            "tutorial",
            "workshop report",
            "competition",
            "challenge report",
        ]

        for pattern in skip_patterns:
            if pattern in title_lower:
                return False

        return True

    def _matches_keywords(self, paper: PaperCandidate, keywords: list[str]) -> bool:
        """키워드 매칭 확인."""
        if not keywords:
            return True

        text = f"{paper.title} {paper.abstract}".lower()
        return any(kw.lower() in text for kw in keywords)
