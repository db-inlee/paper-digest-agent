"""Paper analysis data loader.

Loads extraction, delta, scoring, and verification JSON files
from paper-digest-agent report directories.
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

    return result
