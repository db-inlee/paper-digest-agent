"""Export corpus reports as an Obsidian vault (markdown + wikilinks).

Principle "read in Korean, link in English": human-facing body text stays
Korean; link keys (wikilinks / frontmatter) use the English `name` verbatim.

Usage:
    python -m rtc.obsidian.export

Idempotent: re-running overwrites vault/<slug>.md. Reads reports/ only.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from rtc.config import get_settings
from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput
from rtc.storage.deep_store import DeepStore

logger = logging.getLogger(__name__)


def _yaml_dq(s: str) -> str:
    """Quote a string as a YAML double-quoted scalar (G2/G3)."""
    return '"' + (s or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _related_names(text: str, names: list[str]) -> list[str]:
    """Names that occur in `text` as whole, case-sensitive matches.

    Mitigates over-matching (ticket): word-boundary + case-sensitive +
    longest-match-first so that e.g. "BERT4Rec" does not match inside
    "ContextBERT4Rec", and short acronyms ("R2R") don't match inside larger
    alphanumeric runs.
    """
    matched: list[str] = []
    # longest first so a longer name claims its span before its substrings
    for name in sorted(names, key=len, reverse=True):
        if not name:
            continue
        pattern = r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text):
            # skip if this name is a substring of an already-matched longer one
            if any(name != m and name in m for m in matched):
                continue
            matched.append(name)
    # preserve original (longest-first) discovery but de-dup, stable order
    seen, out = set(), []
    for m in matched:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def note_markdown(extraction: ExtractionOutput, delta: DeltaOutput) -> str:
    """Render one paper note (frontmatter + Korean body + English wikilinks)."""
    baseline_names = [b.name.strip() for b in extraction.baselines if b.name]
    method_names = [m.name.strip() for m in extraction.method_components if m.name]
    link_candidates = baseline_names + method_names

    # --- frontmatter (all-English keys, quoted values) ---
    fm = ["---"]
    fm.append(f"arxiv_id: {_yaml_dq(extraction.arxiv_id)}")
    fm.append(f"title: {_yaml_dq(extraction.title)}")
    fm.append("baselines: [" + ", ".join(_yaml_dq(n) for n in baseline_names) + "]")
    fm.append("methods: [" + ", ".join(_yaml_dq(n) for n in method_names) + "]")
    fm.append("topics: []")
    fm.append("---")

    body = ["", f"# {extraction.title}", ""]
    body.append("## 핵심 요약")
    body.append(delta.one_line_takeaway or "")
    body.append("")

    # 극복 관계 (lineage core)
    body.append("## 극복 관계")
    for cd in delta.core_deltas:
        line = f"- {cd.old_approach} → {cd.new_approach} ({cd.why_better})"
        related = _related_names(
            f"{cd.old_approach} {cd.new_approach}", link_candidates
        )
        if related:
            line += "\n  관련: " + ", ".join(f"[[{n}]]" for n in related)
        body.append(line)
    body.append("")

    # 비교 방법 (baseline list — the edge backbone; names verbatim as wikilinks)
    body.append("## 비교 방법")
    if baseline_names:
        for b in extraction.baselines:
            if b.name:
                body.append(f"- [[{b.name.strip()}]]: {b.description}")
    else:
        body.append("(직접 비교된 baseline 없음)")
    body.append("")

    # 구성 방법 (method components)
    body.append("## 구성 방법")
    for m in extraction.method_components:
        if m.name:
            body.append(f"- [[{m.name.strip()}]]: {m.description}")
    body.append("")

    return "\n".join(fm + body)


def export_vault(reports_dir: Path, vault_dir: Path) -> dict:
    """Convert every paper under reports_dir into vault/<slug>.md.

    G1: iterate reports_dir top-level only; skip hidden (".") dirs and "daily".
    Never recurse (reports/.reextract holds re-extracted copies).
    """
    reports_dir = Path(reports_dir)
    vault_dir = Path(vault_dir)
    vault_dir.mkdir(parents=True, exist_ok=True)
    store = DeepStore(reports_dir.parent, reports_dir=reports_dir)

    written, skipped = 0, 0
    for entry in sorted(reports_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name == "daily":  # G1
            continue
        slug = entry.name
        if not (entry / "extraction.json").exists():
            skipped += 1
            continue
        try:
            extraction = store.load_extraction(slug)
            delta = store.load_delta(slug)
        except Exception as e:
            logger.warning("Skip %s: load failed (%s)", slug, e)
            skipped += 1
            continue
        if extraction is None or delta is None:
            skipped += 1
            continue
        (vault_dir / f"{slug}.md").write_text(
            note_markdown(extraction, delta), encoding="utf-8"
        )
        written += 1

    return {"written": written, "skipped": skipped, "vault": str(vault_dir)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    vault_dir = settings.base_dir / "vault"
    summary = export_vault(settings.reports_dir, vault_dir)
    print("=== Obsidian Export Summary ===")
    print(f"Notes written : {summary['written']}")
    print(f"Skipped       : {summary['skipped']}")
    print(f"Vault         : {summary['vault']}")


if __name__ == "__main__":
    main()
