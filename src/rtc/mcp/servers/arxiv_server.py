"""arXiv MCP Server implementation."""

from datetime import datetime, timedelta
from typing import Any

import arxiv

from rtc.schemas import PaperCandidate


class ArxivServer:
    """MCP Server for arXiv paper search and retrieval."""

    def __init__(self):
        """Initialize arXiv server."""
        self._client = arxiv.Client()

    async def search_papers(
        self,
        categories: list[str] | None = None,
        keywords: list[str] | None = None,
        max_results: int = 100,
        days_back: int = 7,
    ) -> list[dict[str, Any]]:
        """Search for papers on arXiv.

        Args:
            categories: arXiv categories to search (e.g., ["cs.LG", "cs.CL"])
            keywords: Keywords to search in title/abstract
            max_results: Maximum number of results
            days_back: How many days back to search

        Returns:
            List of paper metadata dicts
        """
        # Build query
        query_parts = []

        if categories:
            cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
            query_parts.append(f"({cat_query})")

        if keywords:
            kw_query = " OR ".join(f'all:"{kw}"' for kw in keywords)
            query_parts.append(f"({kw_query})")

        query = " AND ".join(query_parts) if query_parts else "cat:cs.LG"

        # Calculate date cutoff
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Search
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        results = []
        for paper in self._client.results(search):
            # Filter by date
            if paper.published.replace(tzinfo=None) < cutoff_date:
                continue

            results.append({
                "arxiv_id": paper.entry_id.split("/")[-1],
                "title": paper.title,
                "abstract": paper.summary,
                "authors": [a.name for a in paper.authors],
                "categories": paper.categories,
                "published": paper.published.isoformat(),
                "updated": paper.updated.isoformat() if paper.updated else None,
                "pdf_url": paper.pdf_url,
                "comment": paper.comment,
                "journal_ref": paper.journal_ref,
            })

        return results

    async def get_paper_metadata(self, arxiv_id: str) -> dict[str, Any]:
        """Get detailed metadata for a specific paper.

        Args:
            arxiv_id: arXiv paper ID (e.g., "2401.12345")

        Returns:
            Paper metadata dict
        """
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(self._client.results(search))

        return {
            "arxiv_id": arxiv_id,
            "title": paper.title,
            "abstract": paper.summary,
            "authors": [a.name for a in paper.authors],
            "categories": paper.categories,
            "published": paper.published.isoformat(),
            "updated": paper.updated.isoformat() if paper.updated else None,
            "pdf_url": paper.pdf_url,
            "comment": paper.comment,
            "journal_ref": paper.journal_ref,
            "primary_category": paper.primary_category,
            "links": [{"href": l.href, "title": l.title} for l in paper.links],
        }

    async def get_pdf_url(self, arxiv_id: str) -> str:
        """Get the PDF URL for a paper.

        Args:
            arxiv_id: arXiv paper ID

        Returns:
            PDF URL
        """
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def paper_dict_to_candidate(data: dict[str, Any]) -> PaperCandidate:
    """Convert a paper dict to PaperCandidate."""
    return PaperCandidate(
        arxiv_id=data["arxiv_id"],
        title=data["title"],
        abstract=data["abstract"],
        authors=data.get("authors", []),
        categories=data.get("categories", []),
        published=datetime.fromisoformat(data["published"].replace("Z", "+00:00")),
        updated=(
            datetime.fromisoformat(data["updated"].replace("Z", "+00:00"))
            if data.get("updated")
            else None
        ),
        pdf_url=data["pdf_url"],
        comment=data.get("comment"),
        journal_ref=data.get("journal_ref"),
    )
