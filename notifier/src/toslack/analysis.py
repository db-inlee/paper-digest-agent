"""Paper analysis data loader.

Loads extraction, delta, scoring, and verification JSON files
from paper-digest-agent report directories.

This module is the only place in notifier that reads ``reports/<slug>/*.json``,
so schema drift is normalised here once for every consumer (the Slack renderer,
the markdown append path, and the web detail API).
"""

import json
from pathlib import Path
from typing import Any

from .config import settings


def find_paper_dir(arxiv_id: str) -> Path | None:
    """Find the report directory for a given arxiv_id.

    Searches for directories matching ``{arxiv_id}-*`` under
    ``settings.report_base_dir``.
    """
    base = settings.report_base_dir
    if not base.exists():
        return None

    for d in base.iterdir():
        if d.is_dir() and d.name.startswith(f"{arxiv_id}-"):
            return d

    return None


def normalize_benchmarks(extraction: dict[str, Any]) -> None:
    """Fold the legacy singular ``benchmark`` into the plural ``benchmarks`` list.

    Papers written before 2026-02-17 carry a single ``benchmark`` object; newer
    ones carry a ``benchmarks`` list. No paper carries both.

    The singular key is deliberately left in place: the web detail view reads it
    directly, so removing it would blank the benchmark table for every legacy
    paper. This only ever adds.
    """
    merged = list(extraction.get("benchmarks") or [])
    legacy = extraction.get("benchmark")
    if legacy and legacy not in merged:
        merged.append(legacy)
    extraction["benchmarks"] = merged


def load_paper_detail(arxiv_id: str) -> dict[str, Any] | None:
    """Load all analysis JSON files for a paper.

    Returns a combined dict with keys: extraction, delta, scoring, verification.
    Missing files are set to ``None``.
    Returns ``None`` if the paper directory is not found.
    """
    paper_dir = find_paper_dir(arxiv_id)
    if paper_dir is None:
        return None

    result: dict[str, Any] = {"arxiv_id": arxiv_id}

    for key in ("extraction", "delta", "scoring", "verification"):
        json_path = paper_dir / f"{key}.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                result[key] = json.load(f)
        else:
            result[key] = None

    extraction = result.get("extraction")
    if isinstance(extraction, dict):
        normalize_benchmarks(extraction)

    return result
