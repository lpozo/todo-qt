"""Tests for Plan.edit_title, Plan.reschedule, and Plan.set_done."""

from datetime import datetime

import pytest

from todo_qt.domain.errors import EmptyTitleError, EndNotAfterStartError, TaskNotFoundError
from todo_qt.domain.plan import Plan
from todo_qt.domain.task import Task, TaskId, TimeSlot


def _slot(start_hour: int, end_hour: int, start_min: int = 0, end_min: int = 0) -> TimeSlot:
    return TimeSlot(
        datetime(2026, 1, 5, start_hour, start_min),
        datetime(2026, 1, 5, end_hour, end_min),
    )


def _task(task_id: str, title: str, slot: TimeSlot, *, done: bool = False) -> Task:
    return Task(TaskId(task_id), title, slot, done)


def _abc_plan(*, b_done: bool = False) -> Plan:
    return Plan(
        (
            _task("a", "A", _slot(9, 10)),
            _task("b", "Buy milk", _slot(10, 11), done=b_done),
            _task("c", "C", _slot(11, 12)),
        )
    )


def test_edit_title_keeps_position_times_and_done_flag() -> None:
    plan = _abc_plan(b_done=True)

    result = plan.edit_title(TaskId("b"), "Buy oat milk")

    assert result.tasks[1] == _task("b", "Buy oat milk", _slot(10, 11), done=True)
    assert result.tasks[0] == plan.tasks[0]
    assert result.tasks[2] == plan.tasks[2]


def test_edit_title_rejects_blank_title_and_keeps_original() -> None:
    plan = _abc_plan()

    with pytest.raises(EmptyTitleError):
        plan.edit_title(TaskId("b"), "  ")

    assert plan.get(TaskId("b")).title == "Buy milk"


def test_edit_title_unknown_id_raises() -> None:
    with pytest.raises(TaskNotFoundError):
        _abc_plan().edit_title(TaskId("zz"), "x")


def test_reschedule_changes_only_target_task_times() -> None:
    plan = Plan((_task("a", "A", _slot(9, 10)), _task("b", "B", _slot(10, 11))))

    result = plan.reschedule(TaskId("a"), _slot(13, 13, 0, 45))

    assert result.tasks == (_task("a", "A", _slot(13, 13, 0, 45)), plan.tasks[1])


def test_reschedule_may_create_overlap() -> None:
    plan = Plan((_task("a", "A", _slot(9, 10)), _task("b", "B", _slot(10, 11))))

    result = plan.reschedule(TaskId("b"), _slot(9, 10, 30, 30))

    assert result.tasks == (plan.tasks[0], _task("b", "B", _slot(9, 10, 30, 30)))


def test_reschedule_with_end_not_after_start_is_rejected_at_slot_construction() -> None:
    plan = Plan((_task("a", "A", _slot(9, 10)),))

    with pytest.raises(EndNotAfterStartError):
        _slot(10, 9)

    assert plan.tasks[0].slot == _slot(9, 10)


def test_set_done_marks_task_done_in_place() -> None:
    plan = _abc_plan()

    result = plan.set_done(TaskId("b"), True)

    assert result.tasks[1] == _task("b", "Buy milk", _slot(10, 11), done=True)
    assert [t.id for t in result.tasks] == ["a", "b", "c"]


def test_set_done_false_reopens_task() -> None:
    result = _abc_plan(b_done=True).set_done(TaskId("b"), False)

    assert result.get(TaskId("b")).done is False


def test_set_done_is_idempotent() -> None:
    plan = _abc_plan(b_done=True)

    assert plan.set_done(TaskId("b"), True) == plan
