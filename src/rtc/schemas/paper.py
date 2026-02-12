"""Paper-related schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaperCandidate(BaseModel):
    """A candidate paper from arXiv search."""

    arxiv_id: str = Field(..., description="arXiv identifier (e.g., '2401.12345')")
    title: str = Field(..., description="Paper title")
    abstract: str = Field(..., description="Paper abstract")
    authors: list[str] = Field(default_factory=list, description="List of author names")
    categories: list[str] = Field(default_factory=list, description="arXiv categories")
    published: datetime = Field(..., description="Publication date")
    updated: Optional[datetime] = Field(default=None, description="Last update date")
    pdf_url: str = Field(..., description="URL to PDF")
    comment: Optional[str] = Field(default=None, description="Author comments")
    journal_ref: Optional[str] = Field(default=None, description="Journal reference if published")
    # GitHub 정보 (HF Papers에서 제공)
    github_url: Optional[str] = Field(default=None, description="GitHub 레포 URL")
    github_stars: Optional[int] = Field(default=None, description="GitHub 스타 수")
    # 학회/venue 정보 (arXiv comment에서 추출)
    venue: Optional[str] = Field(default=None, description="Detected conference/venue from arXiv comment")
    # 매칭된 키워드
    matched_keywords: list[str] = Field(default_factory=list, description="필터링에 매칭된 키워드")

    @property
    def arxiv_url(self) -> str:
        """Get the arXiv abstract page URL."""
        return f"https://arxiv.org/abs/{self.arxiv_id}"


class SelectedPaper(BaseModel):
    """A paper selected for detailed analysis."""

    paper: PaperCandidate = Field(..., description="The selected paper")
    selection_reason: str = Field(..., description="Reason for selection")
    total_score: int = Field(..., description="Total score from scoring")
    rank: int = Field(default=1, description="Rank among candidates")
