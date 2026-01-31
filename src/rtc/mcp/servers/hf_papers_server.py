"""Hugging Face Papers MCP Server implementation."""

from datetime import datetime, timedelta
from typing import Any

import httpx

from rtc.schemas import PaperCandidate


class HFPapersServer:
    """MCP Server for Hugging Face Daily Papers.

    Provides access to papers featured on Hugging Face's daily papers page.
    """

    BASE_URL = "https://huggingface.co/api/daily_papers"

    def __init__(self):
        """Initialize HF Papers server."""
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _fetch_papers(self, date: str | None = None) -> list[dict[str, Any]]:
        """Fetch papers from Hugging Face API.

        Args:
            date: Optional date string in YYYY-MM-DD format.
                  If None, fetches today's papers.

        Returns:
            List of paper data dicts.
        """
        url = self.BASE_URL
        if date:
            url = f"{url}?date={date}"

        response = await self._client.get(url)
        response.raise_for_status()

        papers = response.json()
        return [self._normalize_paper(p) for p in papers]

    def _normalize_paper(self, paper: dict[str, Any]) -> dict[str, Any]:
        """Normalize paper data to a consistent format.

        Args:
            paper: Raw paper data from HF API.

        Returns:
            Normalized paper dict.
        """
        # Extract paper info from the nested structure
        paper_info = paper.get("paper", {})

        # Extract arxiv_id from the id field (format: "2501.12345")
        arxiv_id = paper_info.get("id", "")

        # Get submitter info
        submitter = paper_info.get("submittedOnDailyBy", {})

        return {
            "arxiv_id": arxiv_id,
            "title": paper_info.get("title", "") or paper.get("title", ""),
            "abstract": paper_info.get("summary", "") or paper.get("summary", ""),
            "authors": [
                author.get("name", "") for author in paper_info.get("authors", [])
            ],
            "url": f"https://huggingface.co/papers/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "votes": paper_info.get("upvotes", 0),
            "submitted_by": submitter.get("user", ""),
            "published": paper_info.get("publishedAt", "") or paper.get("publishedAt", ""),
            "source": "hf_papers",
            # GitHub 정보
            "github_url": paper_info.get("githubRepo"),
            "github_stars": paper_info.get("githubStars"),
        }

    async def get_today_papers(self) -> list[dict[str, Any]]:
        """Get today's papers from Hugging Face.

        Returns:
            List of paper metadata dicts.
        """
        return await self._fetch_papers()

    async def get_yesterday_papers(self) -> list[dict[str, Any]]:
        """Get yesterday's papers from Hugging Face.

        Returns:
            List of paper metadata dicts.
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return await self._fetch_papers(date=yesterday)

    async def get_papers_by_date(self, date: str) -> list[dict[str, Any]]:
        """Get papers for a specific date.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            List of paper metadata dicts.
        """
        return await self._fetch_papers(date=date)

    async def search_papers(
        self,
        days_back: int = 7,
        min_votes: int = 0,
    ) -> list[dict[str, Any]]:
        """Search recent papers with optional vote filter.

        Args:
            days_back: Number of days to search back (default: 7).
            min_votes: Minimum number of upvotes to filter by (default: 0).

        Returns:
            List of paper metadata dicts, sorted by votes descending.
        """
        # 실제 날짜 자동 감지 (시스템 날짜가 미래일 경우 대비)
        base_date = await self._find_latest_date()
        if not base_date:
            return []

        all_papers = []

        for i in range(days_back):
            date = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
            try:
                papers = await self._fetch_papers(date=date)
                all_papers.extend(papers)
            except httpx.HTTPError:
                # Skip days with no data
                continue

        # Filter by minimum votes
        if min_votes > 0:
            all_papers = [p for p in all_papers if p.get("votes", 0) >= min_votes]

        # Sort by votes descending
        all_papers.sort(key=lambda p: p.get("votes", 0), reverse=True)

        return all_papers

    async def _find_latest_date(self) -> datetime | None:
        """Find the latest date with available papers.

        Tries today first, then goes back up to 30 days to find data.

        Returns:
            datetime of latest available date, or None if not found.
        """
        # 시스템 날짜부터 시작
        check_date = datetime.now()

        for _ in range(30):
            date_str = check_date.strftime("%Y-%m-%d")
            try:
                papers = await self._fetch_papers(date=date_str)
                if papers:
                    return check_date
            except httpx.HTTPError:
                pass
            check_date -= timedelta(days=1)

        return None

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


def paper_dict_to_candidate(data: dict[str, Any]) -> PaperCandidate:
    """Convert a HF paper dict to PaperCandidate.

    Args:
        data: Paper data dict from HFPapersServer.

    Returns:
        PaperCandidate instance.
    """
    # Parse published date
    published_str = data.get("published", "")
    if published_str:
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            published = datetime.now()
    else:
        published = datetime.now()

    return PaperCandidate(
        arxiv_id=data["arxiv_id"],
        title=data["title"],
        abstract=data["abstract"],
        authors=data.get("authors", []),
        categories=[],  # HF papers don't provide categories
        published=published,
        updated=None,
        pdf_url=data["pdf_url"],
        comment=None,
        journal_ref=None,
        github_url=data.get("github_url"),
        github_stars=data.get("github_stars"),
    )
