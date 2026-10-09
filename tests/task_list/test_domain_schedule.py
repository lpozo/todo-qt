"""Tests for default_slot and is_overdue."""

from datetime import UTC, datetime, time

import pytest

from todo_qt.domain.errors import NaiveDatetimeRequiredError
from todo_qt.domain.schedule import default_slot, is_overdue
from todo_qt.domain.task import Task, TaskId, TimeSlot


def _task(*, done: bool = False) -> Task:
    slot = TimeSlot(datetime(2026, 1, 2, 9, 0), datetime(2026, 1, 2, 10, 0))
    return Task(TaskId("a"), "Write", slot, done=done)


def _at(hour: int, minute: int = 0, second: int = 0, micro: int = 0) -> datetime:
    return datetime(2026, 1, 2, hour, minute, second, micro)


def test_default_slot_rounds_up_to_next_full_hour() -> None:
    assert default_slot(_at(14, 20)) == TimeSlot(_at(15), _at(15, 30))


def test_default_slot_at_exact_hour_uses_following_hour() -> None:
    assert default_slot(_at(14)) == TimeSlot(_at(15), _at(15, 30))


def test_default_slot_rolls_over_midnight() -> None:
    expected = TimeSlot(datetime(2026, 1, 3, 0, 0), datetime(2026, 1, 3, 0, 30))
    assert default_slot(_at(23, 20)) == expected


def test_default_slot_ignores_seconds() -> None:
    assert default_slot(_at(14, 59, 59, 999999)) == TimeSlot(_at(15), _at(15, 30))


def test_default_slot_rejects_aware_now() -> None:
    with pytest.raises(NaiveDatetimeRequiredError):
        default_slot(datetime(2026, 1, 2, 14, 20, tzinfo=UTC))


def test_default_slot_ignores_day_start() -> None:
    # The function takes no plan, so a day start of 08:00 cannot influence it.
    assert time(8, 0) != _at(15).time()
    assert default_slot(_at(14, 20)) == TimeSlot(_at(15), _at(15, 30))


def test_is_overdue_true_for_open_task_ended_before_now() -> None:
    assert is_overdue(_task(), _at(10, 0, 1)) is True


def test_is_overdue_false_at_exact_end() -> None:
    assert is_overdue(_task(), _at(10, 0)) is False


def test_is_overdue_false_for_done_task() -> None:
    assert is_overdue(_task(done=True), _at(12)) is False


def test_is_overdue_false_for_future_task() -> None:
    assert is_overdue(_task(), _at(9)) is False


def test_is_overdue_returns_after_uncomplete() -> None:
    reopened = _task(done=True)
    reopened = Task(reopened.id, reopened.title, reopened.slot, done=False)
    assert is_overdue(reopened, _at(12)) is True


def test_is_overdue_rejects_aware_now() -> None:
    with pytest.raises(NaiveDatetimeRequiredError):
        is_overdue(_task(), datetime(2026, 1, 2, 12, 0, tzinfo=UTC))
