"""SkimStore/IndexStore must honour an injected directory over base_dir."""

from rtc.storage.index_store import IndexStore
from rtc.storage.skim_store import SkimStore


def test_skim_store_honors_papers_dir_override(tmp_path, make_daily):
    """papers_dir wins over base_dir and the file lands there."""
    base_dir = tmp_path / "repo"
    papers_dir = tmp_path / "volume" / "papers"

    store = SkimStore(base_dir, papers_dir=papers_dir)
    path = store.save(make_daily("2026-08-20", ["1"], ["1"]))

    assert store.papers_dir == papers_dir
    assert path == papers_dir / "2026-08-20.yaml"
    assert path.exists()
    assert not (base_dir / "papers").exists()


def test_skim_store_falls_back_to_base_dir(tmp_path):
    """Without an override the legacy base_dir layout is kept."""
    store = SkimStore(tmp_path)

    assert store.papers_dir == tmp_path / "papers"
    assert store.papers_dir.exists()


def test_index_store_honors_index_dir_override(tmp_path, make_summary):
    """index_dir wins over base_dir and the indexes land there."""
    base_dir = tmp_path / "repo"
    index_dir = tmp_path / "volume" / "index"

    store = IndexStore(base_dir, index_dir=index_dir)
    store.update_by_date("2026-08-20", ["1"])
    store.update_by_tag([make_summary("1")])

    assert store.index_dir == index_dir
    assert (index_dir / "by_date.yaml").exists()
    assert (index_dir / "by_tag.yaml").exists()
    assert not (base_dir / "index").exists()
    assert store.get_by_tag("agent") == ["1"]


def test_index_store_falls_back_to_base_dir(tmp_path):
    """Without an override the legacy base_dir layout is kept."""
    store = IndexStore(tmp_path)

    assert store.index_dir == tmp_path / "index"
    assert store.index_dir.exists()
