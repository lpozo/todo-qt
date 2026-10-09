"""Tests for rejecting and preserving unreadable saved data."""

import json
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from todo_qt.domain import Plan
from todo_qt.persistence import JsonPlanStore, codec
from todo_qt.services import StoreCorruptError, StoreWriteError

from .fakes import MutableClock, T, make_plan, make_slot, make_task


def _document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "day_start": "09:00",
        "tasks": [
            {
                "id": "a",
                "title": "One",
                "start": "2026-01-02T09:00",
                "end": "2026-01-02T10:00",
                "done": False,
            }
        ],
    }
    document.update(overrides)
    return document


def _write(data_dir: Path, content: str | bytes) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "tasks.json"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _task(**overrides: Any) -> dict[str, Any]:
    task: dict[str, Any] = _document()["tasks"][0]
    task.update(overrides)
    return task


def test_store_load_corrupt_data_raises_and_leaves_file_untouched(data_dir: Path) -> None:
    path = _write(data_dir, "{not json")

    with pytest.raises(StoreCorruptError) as info:
        JsonPlanStore(data_dir).load()

    assert info.value.path == path
    assert path.read_text(encoding="utf-8") == "{not json"
    assert [p.name for p in data_dir.iterdir()] == ["tasks.json"]


def test_store_load_rejects_unknown_schema_version(data_dir: Path) -> None:
    _write(data_dir, json.dumps(_document(schema_version=2)))

    with pytest.raises(StoreCorruptError, match="schema_version"):
        JsonPlanStore(data_dir).load()


def test_store_load_rejects_end_not_after_start(data_dir: Path) -> None:
    bad = _task(start="2026-01-02T10:00", end="2026-01-02T09:00")
    _write(data_dir, json.dumps(_document(tasks=[bad])))

    with pytest.raises(StoreCorruptError):
        JsonPlanStore(data_dir).load()


def test_store_save_after_corrupt_load_preserves_unreadable_content(data_dir: Path) -> None:
    _write(data_dir, "garbage")
    clock = MutableClock(T(10, 5))
    store = JsonPlanStore(data_dir, clock)
    with pytest.raises(StoreCorruptError):
        store.load()

    store.save(make_plan(make_task()))

    aside = data_dir / "tasks.20260102-100500.corrupt"
    assert aside.read_text(encoding="utf-8") == "garbage"
    assert JsonPlanStore(data_dir).load() == make_plan(make_task())


def test_store_save_after_corrupt_load_uses_numeric_suffix_on_name_clash(data_dir: Path) -> None:
    _write(data_dir, "second")
    (data_dir / "tasks.20260102-100500.corrupt").write_text("first", encoding="utf-8")
    store = JsonPlanStore(data_dir, MutableClock(T(10, 5)))
    with pytest.raises(StoreCorruptError):
        store.load()

    store.save(make_plan(make_task()))

    assert (data_dir / "tasks.20260102-100500.corrupt").read_text(encoding="utf-8") == "first"
    assert (data_dir / "tasks.20260102-100500.1.corrupt").read_text(encoding="utf-8") == "second"


def test_store_save_without_corrupt_load_creates_no_corrupt_file(data_dir: Path) -> None:
    store = JsonPlanStore(data_dir)

    store.save(make_plan(make_task()))
    store.save(make_plan(make_task(), make_task("b", slot=make_slot(T(10), T(11)))))

    assert not list(data_dir.glob("*.corrupt"))


def test_store_save_raises_and_writes_nothing_when_preserving_fails(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(data_dir, "garbage")
    store = JsonPlanStore(data_dir, MutableClock(T(10, 5)))
    with pytest.raises(StoreCorruptError):
        store.load()

    def fail(*args: object, **kwargs: object) -> None:
        raise PermissionError("nope")

    monkeypatch.setattr("os.rename", fail)

    with pytest.raises(StoreWriteError):
        store.save(make_plan(make_task()))

    assert path.read_text(encoding="utf-8") == "garbage"
    assert sorted(p.name for p in data_dir.iterdir()) == ["tasks.json"]


@pytest.mark.parametrize(
    "content",
    [
        b"\xff\xfe\x00bad",
        "[]",
        "[" * 100000,
        '{"a":' * 100000,
        "null",
        json.dumps(_document(schema_version=True)),
        json.dumps(_document(schema_version="1")),
        json.dumps({k: v for k, v in _document().items() if k != "tasks"}),
        json.dumps(_document(tasks={})),
        json.dumps(_document(day_start="9:00 am")),
        json.dumps(_document(day_start=900)),
        json.dumps(_document(tasks=[_task(start="2026-01-02T09:00:30")])),
        json.dumps(_document(tasks=[_task(start="2026-01-02T09:00Z")])),
        json.dumps(_document(tasks=[_task(done="no")])),
        json.dumps(_document(tasks=[_task(id=5)])),
        json.dumps(_document(tasks=[_task(title="  ")])),
        json.dumps(_document(tasks=[_task(), _task()])),
        json.dumps(_document(tasks=["x"])),
    ],
)
def test_store_load_rejects_invalid_documents(data_dir: Path, content: str | bytes) -> None:
    _write(data_dir, content)

    with pytest.raises(StoreCorruptError):
        JsonPlanStore(data_dir).load()


def test_store_save_retry_after_failed_write_keeps_one_preserved_copy(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(data_dir, "garbage")
    store = JsonPlanStore(data_dir, MutableClock(T(10, 5)))
    with pytest.raises(StoreCorruptError):
        store.load()
    real_replace = os.replace
    attempts: list[int] = []

    def flaky(*args: Any, **kwargs: Any) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("disk full")
        real_replace(*args, **kwargs)

    monkeypatch.setattr("os.replace", flaky)

    with pytest.raises(StoreWriteError):
        store.save(make_plan(make_task()))
    preserved = data_dir / "tasks.20260102-100500.corrupt"
    assert preserved.read_text(encoding="utf-8") == "garbage"
    store.save(make_plan(make_task()))

    assert [p.read_text(encoding="utf-8") for p in data_dir.glob("*.corrupt")] == ["garbage"]
    assert JsonPlanStore(data_dir).load() == make_plan(make_task())


def test_store_load_rejects_unreadable_path(data_dir: Path) -> None:
    (data_dir / "tasks.json").mkdir(parents=True, exist_ok=True)

    with pytest.raises(StoreCorruptError):
        JsonPlanStore(data_dir).load()


def test_store_load_ignores_unknown_extra_fields(data_dir: Path) -> None:
    document = _document(extra=1, tasks=[_task(note="x")])
    _write(data_dir, json.dumps(document))

    plan = JsonPlanStore(data_dir).load()

    assert plan == make_plan(make_task("a", "One"))


_starts = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1)).map(
    lambda d: d.replace(second=0, microsecond=0)
)


@st.composite
def _plans(draw: st.DrawFn) -> Plan:
    tasks = []
    for index in range(draw(st.integers(0, 4))):
        start = draw(_starts)
        end = start + timedelta(minutes=draw(st.integers(1, 5000)))
        title = draw(st.text(min_size=1).filter(lambda s: s.strip() != ""))
        slot = make_slot(start, end)
        tasks.append(make_task(f"id{index}", title, slot, done=draw(st.booleans())))
    day_start = time(draw(st.integers(0, 23)), draw(st.integers(0, 59)))
    return make_plan(*tasks, day_start=day_start)


@given(_plans())
def test_codec_decode_inverts_encode(plan: Plan) -> None:
    assert codec.decode(codec.encode(plan)) == plan
