"""Path overrides must be readable from the environment.

Settings fields carry aliases and populate_by_name is off, so passing a field
name as a keyword is silently ignored - the environment is the only reliable
way to drive these in tests.
"""

from pathlib import Path

from rtc.config import Settings


def test_defaults_derive_from_base_dir(monkeypatch):
    """With nothing set, every directory hangs off base_dir."""
    for name in ("BASE_DIR", "REPORT_BASE_DIR", "PAPERS_BASE_DIR", "INDEX_BASE_DIR"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.papers_dir == settings.base_dir / "papers"
    assert settings.index_dir == settings.base_dir / "index"
    assert settings.reports_dir == settings.base_dir / "reports"


def test_settings_path_overrides_from_env(monkeypatch, tmp_path):
    """Each directory can be redirected independently."""
    monkeypatch.setenv("PAPERS_BASE_DIR", str(tmp_path / "vol" / "papers"))
    monkeypatch.setenv("INDEX_BASE_DIR", str(tmp_path / "vol" / "index"))
    monkeypatch.setenv("REPORT_BASE_DIR", str(tmp_path / "vol" / "reports"))

    settings = Settings()

    assert settings.papers_dir == tmp_path / "vol" / "papers"
    assert settings.index_dir == tmp_path / "vol" / "index"
    assert settings.reports_dir == tmp_path / "vol" / "reports"


def test_base_dir_override_moves_every_directory(monkeypatch, tmp_path):
    """BASE_DIR alone relocates all three defaults."""
    for name in ("REPORT_BASE_DIR", "PAPERS_BASE_DIR", "INDEX_BASE_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BASE_DIR", str(tmp_path / "data"))

    settings = Settings()

    assert settings.base_dir == Path(tmp_path / "data")
    assert settings.papers_dir == tmp_path / "data" / "papers"
    assert settings.index_dir == tmp_path / "data" / "index"
    assert settings.reports_dir == tmp_path / "data" / "reports"


def test_papers_base_dir_wins_over_base_dir(monkeypatch, tmp_path):
    """A specific override beats the common root."""
    monkeypatch.setenv("BASE_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PAPERS_BASE_DIR", str(tmp_path / "elsewhere"))

    settings = Settings()

    assert settings.papers_dir == tmp_path / "elsewhere"
    assert settings.index_dir == tmp_path / "data" / "index"
