"""Tests for Plan.add."""

from datetime import datetime

import pytest

from todo_qt.domain.errors import DuplicateTaskIdError, EmptyTitleError
from todo_qt.domain.plan import Plan
from todo_qt.domain.task import Task, TaskId, TimeSlot


def _slot(start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> TimeSlot:
    return TimeSlot(
        datetime(2026, 1, 5, start_hour, start_minute),
        datetime(2026, 1, 5, end_hour, end_minute),
    )


def _task(task_id: str, title: str = "Existing") -> Task:
    return Task(TaskId(task_id), title, _slot(9, 0, 10, 0))


def test_add_appends_task_at_bottom_not_done() -> None:
    existing = _task("a")
    slot = _slot(15, 0, 15, 30)

    result = Plan((existing,)).add(TaskId("b"), "Buy milk", slot)

    assert result.tasks == (existing, Task(TaskId("b"), "Buy milk", slot, done=False))


def test_add_rejects_whitespace_only_title() -> None:
    plan = Plan((_task("a"),))

    with pytest.raises(EmptyTitleError):
        plan.add(TaskId("b"), "   ", _slot(15, 0, 15, 30))

    assert plan == Plan((_task("a"),))


def test_add_accepts_slot_entirely_in_past() -> None:
    result = Plan().add(TaskId("a"), "Early", _slot(8, 0, 8, 30))

    assert [t.id for t in result.tasks] == [TaskId("a")]


def test_add_rejects_duplicate_id() -> None:
    plan = Plan((_task("a"),))

    with pytest.raises(DuplicateTaskIdError):
        plan.add(TaskId("a"), "Again", _slot(15, 0, 15, 30))


def test_add_strips_title() -> None:
    result = Plan().add(TaskId("a"), "  Buy milk ", _slot(15, 0, 15, 30))

    assert result.tasks[0].title == "Buy milk"
