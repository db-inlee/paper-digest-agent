"""Pydantic models for paper summaries."""

from pydantic import BaseModel


class SkimPaper(BaseModel):
    """스킴 단계만 통과한 논문 간략 정보."""

    title: str
    arxiv_url: str
    matched_keywords: list[str] = []
    category: str = ""
    one_liner: str = ""

    @property
    def arxiv_id(self) -> str:
        """Extract arXiv ID from URL (e.g. '2602.10604')."""
        return self.arxiv_url.rstrip("/").split("/")[-1]


class PaperSummary(BaseModel):
    """Parsed paper information from daily report."""

    title: str
    arxiv_id: str
    arxiv_url: str
    score: int
    max_score: int
    stars: int
    summary: str
    problem: str
    contributions: str
    methodology: str
    when_to_use: str
    when_not_to_use: str
    matched_keywords: list[str] = []
    github_url: str | None = None

    @property
    def star_emoji(self) -> str:
        """Return star emoji representation."""
        return "⭐" * self.stars

    @property
    def has_github(self) -> bool:
        """Check if paper has GitHub implementation."""
        return self.github_url is not None
