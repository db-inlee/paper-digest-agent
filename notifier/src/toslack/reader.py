"""Module for reading markdown reports."""

import os
from datetime import datetime
from pathlib import Path

from .config import settings


def read_daily_report(date: str | None = None) -> str:
    """Read the daily report for the specified date.

    Args:
        date: Date string in YYYY-MM-DD format. If None, reads the latest report.

    Returns:
        Content of the report file.

    Raises:
        FileNotFoundError: If the report file does not exist.
    """
    if date is None:
        date = get_latest_report_date()

    report_path = settings.daily_reports_dir / f"{date}.md"

    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    return report_path.read_text(encoding="utf-8")


def get_latest_report_date() -> str:
    """Get the date of the most recent report.

    Returns:
        Date string in YYYY-MM-DD format.

    Raises:
        FileNotFoundError: If no reports are found.
    """
    reports_dir = settings.daily_reports_dir

    if not reports_dir.exists():
        raise FileNotFoundError(f"Reports directory not found: {reports_dir}")

    report_files = sorted(reports_dir.glob("*.md"), reverse=True)

    if not report_files:
        raise FileNotFoundError(f"No reports found in: {reports_dir}")

    # Extract date from filename (e.g., 2026-01-31.md -> 2026-01-31)
    return report_files[0].stem


def list_available_reports() -> list[str]:
    """List all available report dates.

    Returns:
        List of date strings in YYYY-MM-DD format, sorted descending.
    """
    reports_dir = settings.daily_reports_dir

    if not reports_dir.exists():
        return []

    return sorted([f.stem for f in reports_dir.glob("*.md")], reverse=True)
