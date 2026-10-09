"""Tests for atomic saves and write failures in the JSON store."""

import os
from pathlib import Path

import pytest

from todo_qt.persistence import JsonPlanStore
from todo_qt.services import StoreWriteError

from .fakes import T, make_plan, make_slot, make_task

OLD = make_plan(make_task("a", "Old", make_slot(T(8), T(9))))
NEW = make_plan(make_task("b", "New", make_slot(T(10), T(11))))


def _fail(*args: object, **kwargs: object) -> None:
    raise OSError("boom")


def _saved_store(tmp_path: Path) -> JsonPlanStore:
    store = JsonPlanStore(tmp_path)
    store.save(OLD)
    return store


def _assert_untouched(tmp_path: Path, store: JsonPlanStore) -> None:
    assert store.load() == OLD
    assert [p.name for p in tmp_path.iterdir()] == ["tasks.json"]


@pytest.mark.parametrize("target", ["replace", "fsync"])
def test_store_save_is_atomic_previous_state_survives_failed_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    store = _saved_store(tmp_path)
    monkeypatch.setattr(os, target, _fail)

    with pytest.raises(StoreWriteError):
        store.save(NEW)

    monkeypatch.undo()
    _assert_untouched(tmp_path, store)


def test_store_save_failure_raises_store_write_error(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    store = _saved_store(tmp_path)
    tmp_path.chmod(0o500)
    try:
        with pytest.raises(StoreWriteError) as info:
            store.save(NEW)
    finally:
        tmp_path.chmod(0o700)

    assert info.value.path == tmp_path / "tasks.json"
    assert info.value.reason
    _assert_untouched(tmp_path, store)


def test_store_save_wraps_directory_creation_errors(tmp_path: Path) -> None:
    dangling = tmp_path / "link"
    dangling.symlink_to(tmp_path / "missing")

    with pytest.raises(StoreWriteError):
        JsonPlanStore(dangling).save(NEW)


def test_store_save_cleanup_failure_does_not_mask_original_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _saved_store(tmp_path)
    monkeypatch.setattr(os, "replace", _fail)
    monkeypatch.setattr(Path, "unlink", _fail)

    with pytest.raises(StoreWriteError, match="boom"):
        store.save(NEW)


def test_store_save_succeeds_when_directory_fsync_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonPlanStore(tmp_path)
    real_open = os.open

    def open_dir_fails(path: object, flags: int, *args: int) -> int:
        if path == tmp_path and flags == os.O_RDONLY:
            raise OSError("no dir fsync")
        return real_open(path, flags, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", open_dir_fails)

    store.save(NEW)

    assert store.load() == NEW


def test_store_save_unencodable_title_propagates_and_leaves_no_temp_file(tmp_path: Path) -> None:
    store = _saved_store(tmp_path)
    bad = make_plan(make_task("c", "\ud800", make_slot(T(10), T(11))))

    with pytest.raises(UnicodeEncodeError):
        store.save(bad)

    _assert_untouched(tmp_path, store)


def test_store_save_closes_the_temp_fd_when_fchmod_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _saved_store(tmp_path)
    opened: list[int] = []
    closed: list[int] = []
    real_open, real_close = os.open, os.close

    def spy_open(path: str | Path, flags: int, *args: int) -> int:
        fd = real_open(path, flags, *args)
        opened.append(fd)
        return fd

    def spy_close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr(os, "open", spy_open)
    monkeypatch.setattr(os, "close", spy_close)
    monkeypatch.setattr(os, "fchmod", _fail)

    with pytest.raises(StoreWriteError):
        store.save(NEW)

    monkeypatch.undo()
    assert opened
    assert set(opened) <= set(closed)
    _assert_untouched(tmp_path, store)
