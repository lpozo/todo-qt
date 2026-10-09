"""Shared pytest configuration and fixtures."""

import os

# Must be set before any Qt import so tests run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

# Under `pytest -n auto`, CPU contention makes Hypothesis raise
# FailedHealthCheck(too_slow) ("Input generation is slow") on the plan
# strategy. Suppressing it globally could hide a genuinely slow strategy later.
# The per-example deadline stays on to catch slow code such as Plan.move.
settings.register_profile("todo-qt", suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("todo-qt")


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
