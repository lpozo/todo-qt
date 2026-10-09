"""PlanService.add_task."""

import pytest

from todo_qt.domain import EmptyTitleError, TimeSlot

from .fakes import FakeStore, MakeService, MutableClock, T, make_slot


def test_service_add_task_appends_and_saves(
    make_service: MakeService, clock: MutableClock, fake_store: FakeStore
) -> None:
    clock.set(T(14, 20))
    service = make_service()

    result = service.add_task("Buy milk", TimeSlot(T(15, 0), T(15, 30)))

    task = service.plan.tasks[0]
    assert (len(service.plan.tasks), task.done, result.task_id, fake_store.saves) == (
        1,
        False,
        task.id,
        [service.plan],
    )


def test_service_add_task_blank_title_raises_and_does_not_save(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    service = make_service()

    with pytest.raises(EmptyTitleError):
        service.add_task("  ", make_slot())

    assert (service.plan.tasks, fake_store.save_calls) == ((), 0)


def test_service_add_past_task_is_reported_overdue(
    make_service: MakeService, clock: MutableClock
) -> None:
    clock.set(T(14, 20))
    service = make_service()

    result = service.add_task("Old", make_slot(T(8, 0), T(8, 30)))

    assert result.task_id in service.overdue_ids()
