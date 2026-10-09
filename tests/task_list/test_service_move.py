"""PlanService.move_task."""

from datetime import time

import pytest

from todo_qt.domain import IndexOutOfRangeError, InvalidDayStartError, TaskId, TaskNotFoundError

from .fakes import FakeStore, MakeService, T, make_plan, make_slot, make_task

A, B, C = TaskId("a"), TaskId("b"), TaskId("c")


def _abc() -> FakeStore:
    return FakeStore(
        make_plan(
            make_task("a", "A", make_slot(T(9), T(10))),
            make_task("b", "B", make_slot(T(10), T(11, 30))),
            make_task("c", "C", make_slot(T(14), T(14, 30))),
        )
    )


def test_service_move_task_rechains_and_saves(make_service: MakeService) -> None:
    store = _abc()
    service = make_service(store)

    result = service.move_task(C, 1)

    assert (
        [(t.id, t.slot.start, t.slot.end) for t in service.plan.tasks],
        result.changed,
        result.save_error,
        store.saves,
        result.plan == service.plan,
        result.task_id,
    ) == (
        [("a", T(9), T(10)), ("c", T(10), T(10, 30)), ("b", T(10, 30), T(12))],
        True,
        None,
        [service.plan],
        True,
        None,
    )


def test_service_move_task_to_same_index_does_not_save(make_service: MakeService) -> None:
    store = _abc()
    service = make_service(store)
    before = service.plan

    result = service.move_task(B, 1)

    assert (result.changed, service.plan, store.save_calls) == (False, before, 0)


def test_service_undo_after_move_restores_with_old_times(make_service: MakeService) -> None:
    service = make_service(_abc())
    original_c = service.plan.get(C)
    service.delete_task(C)
    service.move_task(B, 0)
    moved = {t.id: t for t in service.plan.tasks}

    result = service.undo()

    assert (
        [t.id for t in service.plan.tasks],
        service.plan.get(C),
        service.plan.get(A) == moved[A],
        service.plan.get(B) == moved[B],
        result.changed,
        service.can_undo,
    ) == (["b", "a", "c"], original_c, True, True, True, False)


def test_service_move_keeps_undo_slot(make_service: MakeService) -> None:
    service = make_service(_abc())
    service.delete_task(B)
    service.move_task(C, 0)

    service.undo()

    assert "b" in [t.id for t in service.plan.tasks]


def test_service_move_unknown_id_raises_and_changes_nothing(make_service: MakeService) -> None:
    store = _abc()
    service = make_service(store)
    service.delete_task(C)
    before, saves = service.plan, store.save_calls

    with pytest.raises(TaskNotFoundError):
        service.move_task(TaskId("zz"), 0)

    assert (service.plan, store.save_calls, service.can_undo) == (before, saves, True)


def test_service_move_index_out_of_range_raises_and_changes_nothing(
    make_service: MakeService,
) -> None:
    store = _abc()
    service = make_service(store)
    service.delete_task(C)
    before, saves = service.plan, store.save_calls

    with pytest.raises(IndexOutOfRangeError):
        service.move_task(A, 5)

    assert (service.plan, store.save_calls, service.can_undo) == (before, saves, True)


def test_service_set_day_start_with_seconds_raises_and_changes_nothing(
    make_service: MakeService,
) -> None:
    store = _abc()
    service = make_service(store)
    service.delete_task(C)
    before, saves = service.plan, store.save_calls

    with pytest.raises(InvalidDayStartError):
        service.set_day_start(time(8, 0, 30))

    assert (service.plan, store.save_calls, service.can_undo) == (before, saves, True)
