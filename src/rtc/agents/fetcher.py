"""CandidateFetcher 에이전트 - 논문 수집 (비-LLM)."""

import logging
import re
from dataclasses import dataclass

import arxiv

from rtc.agents.base import BaseAgent
from rtc.config import get_settings
from rtc.mcp.servers.hf_papers_server import HFPapersServer, paper_dict_to_candidate
from rtc.schemas import PaperCandidate

logger = logging.getLogger(__name__)


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
    skipped_venue_filter: int = 0
    venue_enriched_count: int = 0


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

        # 2. arXiv comment 보강 (venue 감지용)
        venue_enriched = 0
        if self.settings.venue_filter_enabled:
            venue_enriched = self._enrich_arxiv_comments(candidates)

        # 3. 필터링 적용
        filtered, stats = self._apply_filters(candidates)

        return FetchOutput(
            candidates=filtered,
            total_collected=total_collected,
            total_after_filter=len(filtered),
            skipped_previously_processed=stats["skipped_processed"],
            skipped_keyword_filter=stats["skipped_keyword"],
            skipped_venue_filter=stats.get("skipped_venue", 0),
            venue_enriched_count=venue_enriched,
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
            "skipped_venue": 0,
        }

        keywords = self.settings.get_effective_hf_keywords()

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

            # Venue 필터
            if self.settings.venue_filter_enabled:
                if self.settings.venue_filter_mode == "only" and paper.venue is None:
                    stats["skipped_venue"] += 1
                    continue
                if self.settings.venue_filter_mode == "boost" and paper.venue:
                    paper.matched_keywords.append(f"📍{paper.venue}")

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
        """키워드 매칭 확인. 매칭된 키워드를 paper에 기록."""
        if not keywords:
            return True

        text = f"{paper.title} {paper.abstract}".lower()
        matched = [kw for kw in keywords if kw.lower() in text]
        if matched:
            paper.matched_keywords = matched
            return True
        return False

    def _enrich_arxiv_comments(self, candidates: list[PaperCandidate]) -> int:
        """arXiv API로 comment 필드 보강 및 venue 감지.

        comment가 없는 논문만 대상으로 batch lookup 수행.

        Returns:
            venue가 감지된 논문 수
        """
        # comment가 없는 논문의 arxiv_id 수집
        needs_comment = {
            p.arxiv_id: p for p in candidates if p.comment is None
        }
        if not needs_comment:
            return 0

        id_list = list(needs_comment.keys())
        logger.info("arXiv comment 보강: %d건 조회", len(id_list))

        try:
            client = arxiv.Client()
            search = arxiv.Search(id_list=id_list)
            results = list(client.results(search))
        except Exception:
            logger.warning("arXiv API 조회 실패, comment 보강 건너뜀", exc_info=True)
            return 0

        venue_count = 0
        for result in results:
            arxiv_id = result.entry_id.split("/abs/")[-1]
            # 버전 제거하여 매칭 (예: 2401.12345v2 -> 2401.12345)
            base_id = arxiv_id.split("v")[0]

            paper = needs_comment.get(arxiv_id) or needs_comment.get(base_id)
            if paper is None:
                continue

            if result.comment:
                paper.comment = result.comment
                venue = self._extract_venue(result.comment)
                if venue:
                    paper.venue = venue
                    venue_count += 1

        logger.info("arXiv comment 보강 완료: %d건 중 %d건 venue 감지", len(results), venue_count)
        return venue_count

    def _extract_venue(self, comment: str) -> str | None:
        """arXiv comment에서 학회명 추출.

        두 가지 방식으로 매칭:
        1. 정규식: "Accepted at NeurIPS 2025" 등의 패턴
        2. 직접 매칭: 학회명이 comment에 포함되어 있는지 확인
        """
        conferences = self.settings.venue_filter_conferences

        # 1. 정규식 패턴 매칭
        pattern = r"(?:accepted|published|appearing|to appear)\s+(?:at|in|by)\s+(\w+)"
        match = re.search(pattern, comment, re.IGNORECASE)
        if match:
            detected = match.group(1)
            for conf in conferences:
                if detected.upper() == conf.upper():
                    return conf

        # 2. 직접 매칭 (comment 내에 학회명이 포함된 경우)
        comment_upper = comment.upper()
        for conf in conferences:
            if conf.upper() in comment_upper:
                return conf

        return None
