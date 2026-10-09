"""Shared pytest configuration and fixtures."""

import os

# Must be set before any Qt import so tests run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME and XDG_DATA_HOME at tmp_path so no test touches real user data."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.delenv("TODO_QT_DATA_DIR", raising=False)
    return tmp_path


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """An empty data directory for store tests."""
    path = tmp_path / "data"
    path.mkdir()
    return path
