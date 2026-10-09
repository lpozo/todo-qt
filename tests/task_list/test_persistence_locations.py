"""Tests for the default data directory rules (ADR-0005)."""

from pathlib import Path

from todo_qt.persistence import default_data_dir

HOME = Path("/home/someone")


def test_linux_uses_absolute_xdg_data_home() -> None:
    environ = {"XDG_DATA_HOME": "/custom/data"}

    result = default_data_dir(environ, HOME, "linux")

    assert result == Path("/custom/data/todo-qt")


def test_linux_ignores_relative_xdg_data_home() -> None:
    environ = {"XDG_DATA_HOME": "relative/data"}

    result = default_data_dir(environ, HOME, "linux")

    assert result == HOME / ".local/share/todo-qt"


def test_linux_ignores_empty_xdg_data_home() -> None:
    result = default_data_dir({"XDG_DATA_HOME": ""}, HOME, "linux")

    assert result == HOME / ".local/share/todo-qt"


def test_linux_without_xdg_data_home_uses_local_share() -> None:
    result = default_data_dir({}, HOME, "linux")

    assert result == HOME / ".local/share/todo-qt"


def test_macos_uses_application_support_even_with_xdg_set() -> None:
    environ = {"XDG_DATA_HOME": "/custom/data"}

    result = default_data_dir(environ, HOME, "darwin")

    assert result == HOME / "Library/Application Support/todo-qt"
