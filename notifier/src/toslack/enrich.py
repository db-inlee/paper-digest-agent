"""Fill PaperSummary objects from the structured analysis JSON.

The markdown report is kept as the list source - which papers ran today, in what
order, with what score - because that is the only place the ordering exists. The
per-paper content comes from ``reports/<slug>/*.json`` instead of the markdown,
because delta, benchmarks and verification have no markdown representation at
all and cannot be parsed out of it.

Enrichment is always best-effort: a paper whose JSON directory is missing keeps
whatever the markdown gave it and renders with the same block count.
"""

import re
from typing import Any, Callable

from .analysis import load_paper_detail
from .models import BenchmarkEntry, DeltaAxis, PaperSummary, VerificationSummary

# Similarity floor for attaching a methodology hint to a delta axis. Measured
# over all 33 papers the lowest accepted pair scored 0.200, so this rejects
# nothing today; it exists so that future data with genuinely unrelated text
# stays silent rather than printing a wrong pairing.
HINT_MATCH_THRESHOLD = 0.15

MAX_DELTA_AXES = 3
MAX_BENCHMARKS = 2

_HINT_LIMIT_KO = 46
_HINT_LIMIT_EN = 80
_CLAUSE_ENDINGS = ("를 ", "을 ", "여 ", "고 ", ", ")


def _bigrams(text: str) -> set[str]:
    squeezed = re.sub(r"\s+", "", text)
    return {squeezed[i:i + 2] for i in range(len(squeezed) - 1)}


def _similarity(left: str, right: str) -> float:
    """Overlap coefficient over character bigrams.

    Normalising by the shorter side keeps a short delta phrase matchable against
    a long component description, which is the common shape here.
    """
    a, b = _bigrams(left), _bigrams(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _is_mostly_ascii(text: str) -> bool:
    letters = [c for c in text if not c.isspace()]
    if not letters:
        return False
    return sum(c.isascii() for c in letters) / len(letters) > 0.7


def clip_hint(text: str) -> str:
    """Shorten a methodology hint for a single Slack line.

    English hints get a longer budget and are cut on sentence boundaries -
    clipping Latin script at the Korean character budget lands mid-word and
    reads as corruption.
    """
    collapsed = " ".join(text.split())
    limit = _HINT_LIMIT_EN if _is_mostly_ascii(collapsed) else _HINT_LIMIT_KO
    if len(collapsed) <= limit:
        return collapsed

    window = collapsed[:limit]
    sentence_end = max(window.rfind(". "), window.rfind("; "))
    if sentence_end > limit * 0.4:
        return window[:sentence_end + 1].strip()

    for ending in _CLAUSE_ENDINGS:
        cut = window.rfind(ending)
        if cut > limit * 0.5:
            return window[:cut + len(ending)].strip() + "…"

    return window.rstrip() + "…"


def match_hints(
    deltas: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> list[str | None]:
    """Pair each delta axis with one method component's implementation hint.

    Nothing in the data links the two, so pairing is inferred from text overlap:
    all candidate pairs are scored, then assigned greedily best-first so each
    component is used at most once. Positional pairing was measured to agree 92%
    of the time and to be the wrong one where they disagree.

    Returns a hint per delta axis, None where no component clears the threshold
    or every component is already taken.
    """
    scored: list[tuple[float, int, int]] = []
    for delta_index, delta in enumerate(deltas):
        delta_text = f"{delta.get('axis', '')} {delta.get('new_approach', '')}"
        for comp_index, component in enumerate(components):
            hint = component.get("implementation_hint")
            if not hint:
                continue
            comp_text = " ".join([
                component.get("name", ""),
                component.get("description", ""),
                hint,
            ])
            scored.append((_similarity(delta_text, comp_text), delta_index, comp_index))

    scored.sort(reverse=True)
    hints: list[str | None] = [None] * len(deltas)
    used_deltas: set[int] = set()
    used_components: set[int] = set()
    for score, delta_index, comp_index in scored:
        if score < HINT_MATCH_THRESHOLD:
            break
        if delta_index in used_deltas or comp_index in used_components:
            continue
        used_deltas.add(delta_index)
        used_components.add(comp_index)
        hints[delta_index] = clip_hint(components[comp_index]["implementation_hint"])
    return hints


def _build_delta_axes(detail: dict[str, Any]) -> list[DeltaAxis]:
    delta = detail.get("delta") or {}
    extraction = detail.get("extraction") or {}
    core = (delta.get("core_deltas") or [])[:MAX_DELTA_AXES]
    if not core:
        return []

    hints = match_hints(core, extraction.get("method_components") or [])
    return [
        DeltaAxis(
            axis=entry.get("axis", ""),
            old_approach=entry.get("old_approach", ""),
            new_approach=entry.get("new_approach", ""),
            hint=hint,
        )
        for entry, hint in zip(core, hints)
    ]


def _build_benchmarks(detail: dict[str, Any]) -> tuple[list[BenchmarkEntry], int]:
    """Return the benchmarks to display plus how many exist in total.

    ``load_paper_detail`` has already folded the legacy singular field into the
    plural list, so only the plural key is read here.
    """
    extraction = detail.get("extraction") or {}
    entries = extraction.get("benchmarks") or []
    built = [
        BenchmarkEntry(
            dataset=entry.get("dataset", ""),
            metrics=entry.get("metrics") or [],
            baseline_results=entry.get("baseline_results") or {},
            proposed_results=entry.get("proposed_results") or {},
        )
        for entry in entries
    ]
    return built[:MAX_BENCHMARKS], len(built)


def _build_verification(detail: dict[str, Any]) -> VerificationSummary | None:
    verification = detail.get("verification") or {}
    if "total_claims" not in verification:
        return None
    return VerificationSummary(
        total_claims=verification.get("total_claims", 0),
        verified_count=verification.get("verified_count", 0),
        unverified_count=verification.get("unverified_count", 0),
        contradicted_count=verification.get("contradicted_count", 0),
    )


def enrich_paper(
    paper: PaperSummary,
    loader: Callable[[str], dict[str, Any] | None] = load_paper_detail,
) -> PaperSummary:
    """Return a copy of ``paper`` with the JSON-backed fields filled in.

    A paper with no analysis directory is returned unchanged rather than dropped
    - it still renders, just without the delta and benchmark lines.
    """
    try:
        detail = loader(paper.arxiv_id)
    except Exception:  # noqa: BLE001 - a broken file must not sink the message
        detail = None
    if not detail:
        return paper

    delta = detail.get("delta") or {}
    benchmarks, benchmark_total = _build_benchmarks(detail)
    return paper.model_copy(update={
        "takeaway": delta.get("one_line_takeaway") or "",
        "delta_axes": _build_delta_axes(detail),
        "benchmarks": benchmarks,
        "benchmark_total": benchmark_total,
        "verification": _build_verification(detail),
    })


def enrich_papers(
    papers: list[PaperSummary],
    loader: Callable[[str], dict[str, Any] | None] = load_paper_detail,
) -> list[PaperSummary]:
    """Enrich every paper, preserving order."""
    return [enrich_paper(paper, loader) for paper in papers]
