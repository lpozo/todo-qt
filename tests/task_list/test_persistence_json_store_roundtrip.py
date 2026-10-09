"""Tests for saving and loading the plan through the JSON store."""

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import time
from pathlib import Path

import pytest

from todo_qt.persistence import JsonPlanStore

from .fakes import T, make_plan, make_slot, make_task


def test_store_roundtrip_preserves_order_titles_times_done_and_day_start(data_dir: Path) -> None:
    plan = make_plan(
        make_task("b", "Ünïcode second", make_slot(T(10), T(11))),
        make_task("a", "First", make_slot(T(8, 30), T(9, 45)), done=True),
        make_task("c", "Third", make_slot(T(23), T(23, 59))),
        day_start=time(8, 0),
    )

    JsonPlanStore(data_dir).save(plan)

    assert JsonPlanStore(data_dir).load() == plan


def test_store_files_are_user_only(tmp_path: Path) -> None:
    directory = tmp_path / "new" / "data"

    JsonPlanStore(directory).save(make_plan(make_task()))

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "tasks.json").stat().st_mode) == 0o600


def test_store_save_keeps_existing_directory_mode(data_dir: Path) -> None:
    data_dir.chmod(0o755)

    JsonPlanStore(data_dir).save(make_plan())

    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o755


@contextmanager
def _umask(mask: int) -> Iterator[None]:
    old = os.umask(mask)
    try:
        yield
    finally:
        os.umask(old)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.mark.parametrize("mask", [0o277, 0o000])
def test_store_permissions_are_user_only_under_any_umask(tmp_path: Path, mask: int) -> None:
    leaf = tmp_path / "new" / "sub"

    with _umask(mask):
        JsonPlanStore(leaf).save(make_plan(make_task()))

    assert [_mode(tmp_path / "new"), _mode(leaf), _mode(leaf / "tasks.json")] == [
        0o700,
        0o700,
        0o600,
    ]


def test_store_save_does_not_chmod_existing_ancestors(tmp_path: Path) -> None:
    (tmp_path / "base").mkdir(mode=0o755)
    (tmp_path / "base").chmod(0o755)

    with _umask(0o000):
        JsonPlanStore(tmp_path / "base" / "x").save(make_plan())

    assert _mode(tmp_path / "base") == 0o755


def test_store_save_yields_user_only_file_despite_stale_permissive_temp(data_dir: Path) -> None:
    stale = data_dir / f"tasks.json.{os.getpid()}.tmp"
    stale.write_text("stale")
    stale.chmod(0o644)

    with _umask(0o000):
        JsonPlanStore(data_dir).save(make_plan(make_task()))

    assert _mode(data_dir / "tasks.json") == 0o600
    assert not stale.exists()
