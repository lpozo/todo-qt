"""Tests for TODO_QT_DATA_DIR resolution in todo_qt.cli."""

from pathlib import Path

from todo_qt.cli import resolve_data_dir


def test_resolve_data_dir_uses_env_override() -> None:
    result = resolve_data_dir({"TODO_QT_DATA_DIR": "/tmp/x"}, Path("/default"))

    assert result == Path("/tmp/x")


def test_resolve_data_dir_falls_back_to_default_when_unset() -> None:
    assert resolve_data_dir({}, Path("/default")) == Path("/default")


def test_resolve_data_dir_treats_empty_value_as_unset() -> None:
    assert resolve_data_dir({"TODO_QT_DATA_DIR": ""}, Path("/default")) == Path("/default")


def test_resolve_data_dir_expands_home(isolated_home: Path) -> None:
    result = resolve_data_dir({"TODO_QT_DATA_DIR": "~/data"}, Path("/default"))

    assert result == isolated_home / "data"


def test_resolve_data_dir_makes_relative_path_absolute() -> None:
    result = resolve_data_dir({"TODO_QT_DATA_DIR": "rel/dir"}, Path("/default"))

    assert result == Path.cwd() / "rel" / "dir"
