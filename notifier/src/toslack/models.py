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


class DeltaAxis(BaseModel):
    """One structural change from delta.json, with its methodology hint attached.

    ``hint`` comes from a method component matched by text similarity, not from a
    stored link - the data has no delta-to-component relation. It stays None when
    no component clears the matching threshold.
    """

    axis: str
    old_approach: str
    new_approach: str
    hint: str | None = None


class BenchmarkEntry(BaseModel):
    """One benchmark table from extraction.json."""

    dataset: str
    metrics: list[str] = []
    baseline_results: dict[str, str] = {}
    proposed_results: dict[str, str] = {}

    @property
    def shared_metric_keys(self) -> list[str]:
        """Keys present on both sides, i.e. metric-named rather than system-named.

        Non-empty means baseline and proposed can be shown side by side.
        """
        return [k for k in self.baseline_results if k in self.proposed_results]


class VerificationSummary(BaseModel):
    """Claim verification counts from verification.json."""

    total_claims: int
    verified_count: int
    unverified_count: int = 0
    contradicted_count: int = 0


class PaperSummary(BaseModel):
    """Parsed paper information from daily report.

    The markdown report supplies the list-level fields (title, score, keywords,
    links). The optional fields below are filled from ``reports/<slug>/*.json``
    by :mod:`toslack.enrich` and stay empty when those files are missing.
    """

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

    # Filled from structured JSON; all optional so markdown-only parsing still works.
    takeaway: str = ""
    delta_axes: list[DeltaAxis] = []
    benchmarks: list[BenchmarkEntry] = []
    benchmark_total: int = 0
    verification: VerificationSummary | None = None

    @property
    def star_emoji(self) -> str:
        """Return star emoji representation."""
        return "⭐" * self.stars

    @property
    def has_github(self) -> bool:
        """Check if paper has GitHub implementation."""
        return self.github_url is not None

    @property
    def headline(self) -> str:
        """One-line takeaway, falling back to the markdown summary."""
        return self.takeaway or self.summary
