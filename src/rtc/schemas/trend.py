"""Trend Briefing 스키마 정의."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CountDelta(BaseModel):
    """A counted signal, optionally compared against the previous window."""

    name: str
    count: int
    previous: Optional[int] = Field(
        default=None, description="이전 창 카운트 (비교 대상 없으면 None)"
    )

    @property
    def delta(self) -> Optional[int]:
        """Change against the previous window, or None when incomparable."""
        if self.previous is None:
            return None
        return self.count - self.previous


class TrendRepresentative(BaseModel):
    """One paper standing in for a signal."""

    signal: str
    signal_kind: Literal["keyword", "outside"]
    arxiv_id: str
    title: str
    one_liner: str
    link: str


class TrendSummary(BaseModel):
    """Deterministic aggregation over a window of daily skim outputs."""

    # Window shape
    window_dates: list[str] = Field(default_factory=list)
    window_papers: int = 0
    # Keyword axis covers only records that carry matched_keywords
    keyword_dates: list[str] = Field(default_factory=list)
    keyword_papers: int = 0
    has_previous: bool = False

    # Signals
    keywords: list[CountDelta] = Field(default_factory=list)
    categories: list[CountDelta] = Field(default_factory=list)
    top_tags: list[CountDelta] = Field(default_factory=list)
    outside_signals: list[CountDelta] = Field(
        default_factory=list, description="유효 어휘 밖에서 뜬 태그"
    )
    new_keywords: list[CountDelta] = Field(default_factory=list)
    new_tags: list[CountDelta] = Field(default_factory=list)

    vocabulary_changed: bool = Field(
        default=False, description="창 안에서 유효 어휘 스냅샷이 서로 다른가"
    )
    representatives: list[TrendRepresentative] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True when there is nothing worth rendering."""
        return not self.window_dates or self.window_papers == 0
