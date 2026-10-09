"""PlanService.edit_title, reschedule, set_done."""

from pathlib import Path

import pytest

from todo_qt.domain import EmptyTitleError, TaskId
from todo_qt.services import StoreWriteError

from .fakes import FakeStore, MakeService, MutableClock, T, make_plan, make_slot, make_task

A = TaskId("a")


def test_service_edit_title_saves_new_title(make_service: MakeService) -> None:
    store = FakeStore(make_plan(make_task("a", "Buy milk")))
    service = make_service(store)

    result = service.edit_title(A, "Buy oat milk")

    assert (
        service.plan.tasks[0].title,
        store.saves,
        result.changed,
        result.save_error,
        result.plan,
    ) == ("Buy oat milk", [service.plan], True, None, service.plan)


def test_service_edit_title_blank_keeps_original_and_does_not_save(
    make_service: MakeService,
) -> None:
    store = FakeStore(make_plan(make_task("a", "Buy milk")))
    service = make_service(store)

    with pytest.raises(EmptyTitleError):
        service.edit_title(A, " ")

    assert (service.plan.tasks[0].title, store.save_calls) == ("Buy milk", 0)


def test_service_edit_title_save_failure_keeps_change_in_memory(
    make_service: MakeService,
) -> None:
    original = make_plan(make_task("a", "Buy milk"))
    store = FakeStore(original)
    service = make_service(store)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    store.fail_next_save(error)

    result = service.edit_title(A, "Buy oat milk")

    assert (
        result.save_error,
        result.changed,
        service.plan.tasks[0].title,
        store.plan,
    ) == (error, True, "Buy oat milk", original)


def test_service_reschedule_saves_and_leaves_others(make_service: MakeService) -> None:
    other = make_task("b", "B", make_slot(T(10), T(11)))
    store = FakeStore(make_plan(make_task("a", "A"), other))
    service = make_service(store)
    new_slot = make_slot(T(13), T(13, 45))

    result = service.reschedule(A, new_slot)

    assert (
        service.plan.tasks[0].slot,
        service.plan.tasks[1],
        store.saves,
        result.changed,
        result.save_error,
        result.plan,
    ) == (new_slot, other, [service.plan], True, None, service.plan)


def test_service_reschedule_save_failure_keeps_change_in_memory(
    make_service: MakeService,
) -> None:
    original = make_plan(make_task("a", "A"))
    store = FakeStore(original)
    service = make_service(store)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    store.fail_next_save(error)
    new_slot = make_slot(T(13), T(14))

    result = service.reschedule(A, new_slot)

    assert (
        result.save_error,
        result.changed,
        service.plan.tasks[0].slot,
        store.plan,
    ) == (error, True, new_slot, original)


def test_service_reschedule_same_slot_does_not_save(make_service: MakeService) -> None:
    task = make_task("a")
    store = FakeStore(make_plan(task))
    service = make_service(store)

    result = service.reschedule(A, task.slot)

    assert (result.changed, store.save_calls, result.plan) == (False, 0, service.plan)


def test_service_set_done_saves(make_service: MakeService) -> None:
    store = FakeStore(make_plan(make_task("a")))
    service = make_service(store)

    result = service.set_done(A, True)

    assert (
        service.plan.tasks[0].done,
        store.saves,
        result.changed,
        result.save_error,
        result.plan,
    ) == (True, [service.plan], True, None, service.plan)


def test_service_set_done_save_failure_keeps_change_in_memory(
    make_service: MakeService,
) -> None:
    original = make_plan(make_task("a"))
    store = FakeStore(original)
    service = make_service(store)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    store.fail_next_save(error)

    result = service.set_done(A, True)

    assert (
        result.save_error,
        result.changed,
        service.plan.tasks[0].done,
        store.plan,
    ) == (error, True, True, original)


def test_service_set_done_same_value_does_not_save(make_service: MakeService) -> None:
    store = FakeStore(make_plan(make_task("a", done=True)))
    service = make_service(store)

    result = service.set_done(A, True)

    assert (result.changed, store.save_calls, result.plan) == (False, 0, service.plan)


def test_service_uncomplete_makes_past_task_overdue_again(
    make_service: MakeService, clock: MutableClock
) -> None:
    clock.set(T(12))
    store = FakeStore(make_plan(make_task("a", slot=make_slot(T(9), T(10)), done=True)))
    service = make_service(store)

    service.set_done(A, False)

    assert service.is_overdue(A)
