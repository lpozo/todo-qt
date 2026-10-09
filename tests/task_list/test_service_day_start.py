"""PlanService.set_day_start."""

from datetime import time

from todo_qt.domain import TaskId

from .fakes import FakeStore, MakeService, MutableClock, T, make_plan, make_slot, make_task


def _two() -> FakeStore:
    return FakeStore(
        make_plan(
            make_task("a", "A", make_slot(T(10), T(11))),
            make_task("b", "B", make_slot(T(11), T(12))),
        )
    )


def test_service_set_day_start_saves_new_day_start_and_rechains(
    make_service: MakeService,
) -> None:
    store = _two()
    service = make_service(store)

    result = service.set_day_start(time(8, 0))

    assert (
        [(t.slot.start, t.slot.end) for t in service.plan.tasks],
        store.saves[-1].day_start,
        store.save_calls,
        result.changed,
        result.plan == service.plan,
        result.task_id,
    ) == ([(T(8), T(9)), (T(9), T(10))], time(8, 0), 1, True, True, None)


def test_service_set_day_start_on_empty_list_saves_day_start(make_service: MakeService) -> None:
    store = FakeStore()
    service = make_service(store)

    service.set_day_start(time(7, 0))

    assert (store.save_calls, store.saves[-1].day_start, store.saves[-1].tasks) == (
        1,
        time(7, 0),
        (),
    )


def test_service_day_start_survives_restart(make_service: MakeService) -> None:
    store = _two()
    make_service(store).set_day_start(time(8, 0))

    restarted = make_service(store)

    assert restarted.plan.day_start == time(8, 0)


def test_service_add_task_after_day_start_change_still_prefills_next_hour(
    make_service: MakeService, clock: MutableClock
) -> None:
    clock.set(T(14, 20))
    service = make_service(FakeStore())
    service.set_day_start(time(8, 0))

    slot = service.default_slot()

    assert (slot.start, slot.end) == (T(15), T(15, 30))


def test_service_set_day_start_keeps_undo_slot(make_service: MakeService) -> None:
    service = make_service(_two())
    service.delete_task(TaskId("a"))

    service.set_day_start(time(8, 0))

    assert service.can_undo
    service.undo()
    assert [t.id for t in service.plan.tasks] == ["a", "b"]


def test_service_set_day_start_same_value_does_not_save(make_service: MakeService) -> None:
    store = _two()
    service = make_service(store)

    result = service.set_day_start(time(9, 0))

    assert (result.changed, store.save_calls, result.plan == service.plan) == (False, 0, True)
