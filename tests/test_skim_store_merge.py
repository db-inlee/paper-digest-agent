"""SkimStore must never silently drop already-stored skim records."""

from datetime import datetime

import yaml
from rtc.storage.skim_store import SkimStore


def test_skim_store_merges_on_same_date_save(tmp_path, make_daily):
    """A same-date rerun keeps every record from the earlier run."""
    store = SkimStore(tmp_path)

    store.save(make_daily("2026-08-20", ["1", "2", "3"], ["1", "2", "3"]))

    # A rerun sees a different candidate set: papers already deep-analysed are
    # filtered out upstream, so run 2 is structurally a partial set.
    store.save(
        make_daily(
            "2026-08-20",
            ["3", "4", "5"],
            ["4", "5"],
            one_liner="refreshed",
            total_collected=8,
        )
    )

    merged = store.load("2026-08-20")

    assert [p.arxiv_id for p in merged.papers] == ["1", "2", "3", "4", "5"]
    # Collision resolves to the fresh record, untouched records keep their text.
    assert merged.papers[2].one_liner == "refreshed"
    assert merged.papers[0].one_liner == "summary"
    assert merged.deep_candidates == ["1", "2", "3", "4", "5"]


def test_merge_keeps_counters_from_the_latest_run(tmp_path, make_daily):
    """Run-level counters describe the latest run, not the merged union."""
    store = SkimStore(tmp_path)

    store.save(make_daily("2026-08-20", ["1", "2"], ["1"], total_collected=10))
    store.save(
        make_daily(
            "2026-08-20",
            ["3"],
            ["3"],
            total_collected=8,
            total_after_filter=3,
            skipped_keyword_filter=5,
            effective_keywords=["agent", "RAG"],
        )
    )

    merged = store.load("2026-08-20")

    assert len(merged.papers) == 3
    assert merged.total_collected == 8
    assert merged.total_skimmed == 1
    assert merged.total_after_filter == 3
    assert merged.skipped_keyword_filter == 5
    assert merged.effective_keywords == ["agent", "RAG"]


def test_merge_keeps_previous_keyword_snapshot_when_the_new_run_has_none(
    tmp_path, make_daily
):
    """An empty snapshot must not erase the one already on disk."""
    store = SkimStore(tmp_path)

    store.save(make_daily("2026-08-20", ["1"], [], effective_keywords=["agent"]))
    store.save(make_daily("2026-08-20", ["2"], []))

    assert store.load("2026-08-20").effective_keywords == ["agent"]


def test_unreadable_yaml_is_backed_up_instead_of_overwritten(tmp_path, make_daily):
    """A corrupt file is moved aside so the fresh run can still be saved."""
    store = SkimStore(tmp_path)
    path = tmp_path / "papers" / "2026-08-20.yaml"
    path.write_text("papers: [unterminated\n", encoding="utf-8")

    store.save(make_daily("2026-08-20", ["1"], ["1"]))

    backups = list(path.parent.glob("2026-08-20.yaml.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "papers: [unterminated\n"
    assert [p.arxiv_id for p in store.load("2026-08-20").papers] == ["1"]


def test_first_save_writes_the_record_unchanged(tmp_path, make_daily):
    """No prior file means no merge - the run is stored as-is."""
    store = SkimStore(tmp_path)
    store.save(make_daily("2026-08-20", ["1", "2"], ["1"]))

    raw = (tmp_path / "papers" / "2026-08-20.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    assert [p["arxiv_id"] for p in data["papers"]] == ["1", "2"]
    assert isinstance(datetime.fromisoformat(data["skimmed_at"]), datetime)
