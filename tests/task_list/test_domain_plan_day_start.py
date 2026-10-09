"""Tests for Plan.set_day_start and day-start validation."""

from datetime import UTC, date, time

import pytest

from todo_qt.domain import InvalidDayStartError, Plan, TaskId

from .fakes import FRI, T, make_plan, make_slot, make_task

SAT = date(2026, 1, 3)


def test_set_day_start_rechains_from_first_task() -> None:
    plan = make_plan(
        make_task("A", slot=make_slot(T(10), T(11))),
        make_task("B", slot=make_slot(T(11), T(12))),
        day_start=time(9, 0),
    )

    result = plan.set_day_start(time(8, 0))

    assert result.day_start == time(8, 0)
    assert [(t.slot.start, t.slot.end) for t in result.tasks] == [(T(8), T(9)), (T(9), T(10))]


def test_set_day_start_on_empty_plan_only_changes_day_start() -> None:
    result = Plan().set_day_start(time(7, 30))

    assert result.tasks == ()
    assert result.day_start == time(7, 30)


def test_set_day_start_to_same_value_is_noop() -> None:
    plan = make_plan(make_task("A", slot=make_slot(T(10), T(11))), day_start=time(9, 0))

    assert plan.set_day_start(time(9, 0)) == plan


def test_set_day_start_rechain_crosses_midnight() -> None:
    plan = make_plan(
        make_task("A", slot=make_slot(T(10), T(23, 30))),
        make_task("B", slot=make_slot(T(23, 30), T(23, 50))),
    )

    result = plan.set_day_start(time(22, 0))

    assert [(t.slot.start, t.slot.end) for t in result.tasks] == [
        (T(22), T(11, 30, day=SAT)),
        (T(11, 30, day=SAT), T(11, 50, day=SAT)),
    ]


def test_set_day_start_rejects_seconds() -> None:
    with pytest.raises(InvalidDayStartError):
        Plan().set_day_start(time(8, 0, 30))


def test_set_day_start_rechains_done_tasks_too() -> None:
    plan = make_plan(
        make_task("A", slot=make_slot(T(10), T(11)), done=True),
        make_task("B", slot=make_slot(T(11), T(12))),
    )

    result = plan.set_day_start(time(8, 0))

    assert result.get(TaskId("A")).done is True
    assert [(t.slot.start, t.slot.end) for t in result.tasks] == [(T(8), T(9)), (T(9), T(10))]


def test_plan_rejects_aware_day_start() -> None:
    with pytest.raises(InvalidDayStartError):
        Plan(day_start=time(9, 0, tzinfo=UTC))


def test_set_day_start_keeps_first_tasks_own_date() -> None:
    plan = make_plan(make_task("A", slot=make_slot(T(10, day=SAT), T(11, day=SAT))))

    result = plan.set_day_start(time(8, 0))

    assert result.tasks[0].slot.start == T(8, day=SAT)
    assert FRI != SAT


def test_plan_rejects_microseconds_in_day_start() -> None:
    with pytest.raises(InvalidDayStartError):
        Plan(day_start=time(8, 0, 0, 5))


def test_set_day_start_rejects_microseconds() -> None:
    with pytest.raises(InvalidDayStartError):
        Plan().set_day_start(time(8, 0, 0, 5))


def test_set_day_start_rechains_a_single_task() -> None:
    plan = make_plan(make_task("A", slot=make_slot(T(10), T(10, 30))))

    result = plan.set_day_start(time(8, 0))

    assert (result.tasks[0].slot.start, result.tasks[0].slot.end) == (T(8), T(8, 30))
