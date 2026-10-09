"""Tests for the task value types."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from todo_qt.domain.errors import (
    EmptyTitleError,
    EndNotAfterStartError,
    InvalidTimeSlotError,
)
from todo_qt.domain.task import (
    RemovedEntry,
    RemovedTasks,
    Task,
    TaskId,
    TimeSlot,
    normalize_title,
)


def _t(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 9, hour, minute)


def _slot() -> TimeSlot:
    return TimeSlot(_t(15), _t(15, 30))


def test_normalize_title_strips_surrounding_whitespace() -> None:
    assert normalize_title("  Buy milk \t") == "Buy milk"


def test_normalize_title_rejects_whitespace_only() -> None:
    with pytest.raises(EmptyTitleError):
        normalize_title("   \n")


def test_normalize_title_rejects_empty_string() -> None:
    with pytest.raises(EmptyTitleError):
        normalize_title("")


def test_time_slot_accepts_end_after_start() -> None:
    assert TimeSlot(_t(15), _t(15, 30)).duration == timedelta(minutes=30)


def test_time_slot_rejects_end_equal_to_start() -> None:
    with pytest.raises(EndNotAfterStartError):
        TimeSlot(_t(15), _t(15))


def test_time_slot_rejects_end_before_start() -> None:
    with pytest.raises(EndNotAfterStartError):
        TimeSlot(_t(15), _t(14))


def test_time_slot_rejects_timezone_aware_datetime() -> None:
    with pytest.raises(InvalidTimeSlotError):
        TimeSlot(_t(15).replace(tzinfo=UTC), _t(16))


def test_time_slot_rejects_non_zero_seconds() -> None:
    with pytest.raises(InvalidTimeSlotError) as info:
        TimeSlot(_t(15).replace(second=30), _t(16))
    assert not isinstance(info.value, EndNotAfterStartError)


def test_time_slot_rejects_microseconds() -> None:
    with pytest.raises(InvalidTimeSlotError):
        TimeSlot(_t(15), _t(16).replace(microsecond=1))


def test_time_slot_reports_invalid_before_mis_ordered() -> None:
    with pytest.raises(InvalidTimeSlotError) as info:
        TimeSlot(_t(15, 0).replace(tzinfo=UTC), _t(14))
    assert not isinstance(info.value, EndNotAfterStartError)


def test_time_slot_spans_midnight() -> None:
    slot = TimeSlot(_t(23, 30), datetime(2026, 10, 10, 0, 15))
    assert slot.duration == timedelta(minutes=45)


@given(
    start=st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1)),
    minutes=st.integers(min_value=1, max_value=10_000),
)
def test_time_slot_duration_matches_end_minus_start(start: datetime, minutes: int) -> None:
    start = start.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=minutes)
    assert TimeSlot(start, end).duration == end - start


def test_task_defaults_to_not_done() -> None:
    assert Task(TaskId("a"), "Buy milk", _slot()).done is False


def test_task_rejects_blank_title() -> None:
    with pytest.raises(EmptyTitleError):
        Task(TaskId("a"), "  ", _slot())


def _entry(index: int) -> RemovedEntry:
    return RemovedEntry(index, Task(TaskId(f"t{index}"), "x", _slot()))


def test_removed_tasks_accepts_ascending_indexes() -> None:
    assert RemovedTasks((_entry(0), _entry(2))).entries[1].index == 2


@pytest.mark.parametrize(
    "indexes", [(), (2, 1), (1, 1), (-1, 0)], ids=["empty", "desc", "dup", "negative"]
)
def test_removed_tasks_rejects_invalid_indexes(indexes: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        RemovedTasks(tuple(_entry(i) for i in indexes))
