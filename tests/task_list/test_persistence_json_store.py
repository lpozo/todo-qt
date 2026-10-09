"""Tests for the JSON plan store skeleton."""

from pathlib import Path

from todo_qt.persistence import JsonPlanStore


def test_store_load_returns_none_when_nothing_saved(data_dir: Path) -> None:
    store = JsonPlanStore(data_dir)

    assert store.load() is None
