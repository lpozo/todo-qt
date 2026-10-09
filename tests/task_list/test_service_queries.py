"""PlanService queries: now, default_slot, is_overdue, overdue_ids."""

from datetime import timedelta

import pytest

from todo_qt.domain import TaskId, TaskNotFoundError, TimeSlot
from todo_qt.services import PlanService

from .fakes import FakeStore, MakeService, MutableClock, T, make_plan, make_slot, make_task


def test_service_default_slot_uses_injected_clock(
    make_service: MakeService, clock: MutableClock
) -> None:
    clock.set(T(14, 20))

    assert make_service().default_slot() == TimeSlot(T(15, 0), T(15, 30))


def test_service_overdue_ids_reflect_clock_advancing(
    make_service: MakeService, clock: MutableClock
) -> None:
    task = make_task("a", slot=make_slot(T(14, 0), T(14, 30)))
    service = make_service(FakeStore(make_plan(task)))
    clock.set(T(14, 29))
    before = service.overdue_ids()

    clock.advance(timedelta(minutes=2))

    assert (before, service.overdue_ids()) == (frozenset(), frozenset({TaskId("a")}))


def test_service_overdue_ids_exclude_done_tasks(make_service: MakeService) -> None:
    past = make_slot(T(8, 0), T(8, 30))
    store = FakeStore(make_plan(make_task("a", slot=past, done=True), make_task("b", slot=past)))

    assert make_service(store).overdue_ids() == frozenset({TaskId("b")})


def test_service_is_overdue_unknown_id_raises(make_service: MakeService) -> None:
    service: PlanService = make_service()

    with pytest.raises(TaskNotFoundError):
        service.is_overdue(TaskId("nope"))
