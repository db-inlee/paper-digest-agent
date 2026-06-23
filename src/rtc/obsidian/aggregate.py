"""Read-time baseline aggregation with confidence labels (no extraction edit).

Promotes benchmark `baseline_results` keys into the baseline view that the
extractor under-captures, without dropping anything: every candidate is kept
and labeled by *structural* signals (no keyword dictionary).

Labels:
- model     : clean model/method baseline (proper-noun key, well-formed score).
- metric    : likely a metric (key has @<digit>, or % value with a non-model key).
- generic   : obviously-generic placeholder (rarely assignable from structure).
- uncertain : boundary kept for safety (non-standard value, %-on-model-like key,
              combo fragments). Still linked downstream — nothing is lost.

Pure function: dict in, list out. Does not touch extraction.json.
"""

from __future__ import annotations

import re

# Structural signals (NOT keyword lists).
_AT_DIGIT = re.compile(r"@\d")
# proper-noun-ish: a digit, internal camelCase, or a 2+ uppercase run.
# (Hyphen alone is not a model signal: "First-call accuracy" is a metric, not a model.)
_PROPER_NOUN = re.compile(r"\d|[a-z][A-Z]|[A-Z]{2,}")
# a well-formed score value: a number, optionally %, optionally a small set joined
# by commas/slashes (e.g. "33.33", "50.1%", "33.33, 40.65"). Anything else (colons,
# letters mixed in like "Level 1: Exec 46.0") is treated as non-standard -> uncertain.
_SCORE_VALUE = re.compile(r"^\s*\d+(?:\.\d+)?\s*%?(?:\s*[,/]\s*\d+(?:\.\d+)?\s*%?)*\s*$")

COMBO_SEP = " + "


def _looks_like_model(key: str) -> bool:
    return bool(_PROPER_NOUN.search(key))


def _is_standard_score(value: str) -> bool:
    return bool(_SCORE_VALUE.match(value or ""))


def label_key(key: str, value: str) -> str:
    """Label a single baseline_results key by structural signals."""
    # 1) @<digit> in the key is a strong metric signal (NDCG@5, Recall@10).
    if _AT_DIGIT.search(key):
        return "metric"
    # 2) non-standard value (colon, embedded text, ranges) -> uncertain.
    #    Takes priority over proper-noun so e.g. cudaLLM:"Level 1: Exec 46.0..." -> uncertain,
    #    and generalizes to any future malformed value.
    if value is not None and not _is_standard_score(value):
        return "uncertain"
    has_pct = "%" in (value or "")
    if has_pct:
        # % present: a model-looking key is a boundary (e.g. SigLIP2 -> 50.1%),
        # a plain-word key looks like a metric (e.g. "Sequence accuracy" -> 16.94%).
        return "uncertain" if _looks_like_model(key) else "metric"
    # 3) clean numeric score, model-like key -> model.
    return "model"


def aggregate_baselines(extraction: dict) -> list[dict]:
    """Aggregate baselines[] + benchmark baseline_results into a labeled view.

    Returns a list of {name, label, source}. Nothing is dropped:
    - baselines[] entries: label=model, source="baselines".
    - baseline_results keys: structural label, source="benchmark".
    - combo keys ("A + B"): original kept (labeled normally) PLUS each fragment
      added as a bonus uncertain candidate (never replaces the original).
    - dedup on exact string match; an existing baselines[] (model) wins.
    """
    items: list[dict] = []
    seen: dict[str, int] = {}  # name -> index in items

    def add(name: str, label: str, source: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        if name in seen:
            # dedup: prefer model over weaker labels; keep existing source.
            idx = seen[name]
            if items[idx]["label"] != "model" and label == "model":
                items[idx]["label"] = "model"
            return
        seen[name] = len(items)
        items.append({"name": name, "label": label, "source": source})

    # existing baselines[] are model by definition
    for b in extraction.get("baselines", []) or []:
        add(b.get("name", ""), "model", "baselines")

    # benchmark baseline_results keys
    benches = list(extraction.get("benchmarks", []) or [])
    legacy = extraction.get("benchmark")
    if legacy:
        benches.append(legacy)
    for bench in benches:
        for key, value in (bench.get("baseline_results") or {}).items():
            key = (key or "").strip()
            if not key:
                continue
            add(key, label_key(key, value), "benchmark")  # original kept
            if COMBO_SEP in key:  # bonus fragments, always uncertain
                for frag in key.split(COMBO_SEP):
                    add(frag, "uncertain", "benchmark")

    return items


def label_distribution(items: list[dict]) -> dict[str, int]:
    """Count items per label."""
    dist: dict[str, int] = {}
    for it in items:
        dist[it["label"]] = dist.get(it["label"], 0) + 1
    return dist
