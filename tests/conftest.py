"""Shared fixtures for the storage tests."""

from pathlib import Path

import pytest
from rtc.schemas.skim import DailySkimOutput, SkimSummary

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding checked-in sample files (copies, never live data)."""
    return FIXTURES_DIR


@pytest.fixture
def make_summary():
    """Factory for a minimal valid SkimSummary."""

    def _make(arxiv_id: str, one_liner: str = "summary") -> SkimSummary:
        return SkimSummary(
            arxiv_id=arxiv_id,
            title=f"Paper {arxiv_id}",
            one_liner=one_liner,
            tags=["agent"],
            interest_score=4,
            interest_reason="reason",
            category="agent",
            link=f"https://arxiv.org/abs/{arxiv_id}",
            matched_keywords=["agent"],
        )

    return _make


@pytest.fixture
def make_daily(make_summary):
    """Factory for a DailySkimOutput built from plain arxiv ids."""

    def _make(
        date: str,
        ids: list[str],
        deep: list[str],
        one_liner: str = "summary",
        **kwargs,
    ) -> DailySkimOutput:
        kwargs.setdefault("total_collected", 10)
        return DailySkimOutput(
            date=date,
            total_skimmed=len(ids),
            papers=[make_summary(i, one_liner) for i in ids],
            deep_candidates=deep,
            **kwargs,
        )

    return _make
