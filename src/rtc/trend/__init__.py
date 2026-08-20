"""Trend briefing - deterministic aggregation over accumulated skim data."""

from rtc.trend.aggregate import aggregate_trends
from rtc.trend.render import render_trend_section

__all__ = [
    "aggregate_trends",
    "render_trend_section",
]
