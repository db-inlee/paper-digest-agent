"""Pre-existing skim files must keep loading after the schema grew."""

import shutil

from rtc.schemas.skim import DailySkimOutput
from rtc.storage.skim_store import SkimStore

LEGACY_FIXTURE = "legacy_skim_2026-02-13.yaml"
LEGACY_DATE = "2026-02-13"


def _install_fixture(fixtures_dir, tmp_path):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixtures_dir / LEGACY_FIXTURE, papers_dir / f"{LEGACY_DATE}.yaml")
    return papers_dir


def test_daily_skim_output_loads_legacy_yaml(fixtures_dir, tmp_path):
    """A file written before the funnel fields existed still parses."""
    papers_dir = _install_fixture(fixtures_dir, tmp_path)
    store = SkimStore(tmp_path, papers_dir=papers_dir)

    loaded = store.load(LEGACY_DATE)

    assert isinstance(loaded, DailySkimOutput)
    assert len(loaded.papers) == loaded.total_skimmed
    # New optional fields default instead of raising.
    assert loaded.total_after_filter is None
    assert loaded.skipped_duplicate is None
    assert loaded.effective_keywords == []


def test_legacy_file_survives_a_rerun(fixtures_dir, tmp_path, make_daily):
    """Saving over a legacy file merges rather than discards its records."""
    papers_dir = _install_fixture(fixtures_dir, tmp_path)
    store = SkimStore(tmp_path, papers_dir=papers_dir)
    legacy_ids = [p.arxiv_id for p in store.load(LEGACY_DATE).papers]

    store.save(
        make_daily(
            LEGACY_DATE,
            ["9999.00001"],
            ["9999.00001"],
            total_after_filter=1,
            effective_keywords=["agent"],
        )
    )

    merged = store.load(LEGACY_DATE)
    merged_ids = [p.arxiv_id for p in merged.papers]

    assert merged_ids == legacy_ids + ["9999.00001"]
    assert merged.total_after_filter == 1
    assert merged.effective_keywords == ["agent"]
