"""PlanService.delete_task, clear_completed, undo."""

from pathlib import Path

from todo_qt.domain import TaskId
from todo_qt.services import PlanService, StoreWriteError

from .fakes import FakeStore, MakeService, T, make_plan, make_slot, make_task

A, B, C, D = TaskId("a"), TaskId("b"), TaskId("c"), TaskId("d")


def _abc() -> FakeStore:
    return FakeStore(
        make_plan(
            make_task("a", "A", make_slot(T(9), T(10))),
            make_task("b", "B", make_slot(T(10), T(11))),
            make_task("c", "C", make_slot(T(11), T(12))),
        )
    )


def _ids(service: PlanService) -> list[str]:
    return [task.id for task in service.plan.tasks]


def test_service_new_session_has_no_undo(make_service: MakeService) -> None:
    store = _abc()
    make_service(store).delete_task(B)
    saves = store.save_calls
    fresh = make_service(store)

    result = fresh.undo()

    assert (fresh.can_undo, result.changed, _ids(fresh), store.save_calls) == (
        False,
        False,
        ["a", "c"],
        saves,
    )


def test_service_delete_removes_task_and_saves(make_service: MakeService) -> None:
    store = _abc()
    service = make_service(store)
    before = service.plan

    result = service.delete_task(B)

    assert (
        _ids(service),
        service.plan.tasks == (before.tasks[0], before.tasks[2]),
        store.saves,
        service.can_undo,
        result.changed,
        result.save_error,
    ) == (["a", "c"], True, [service.plan], True, True, None)


def test_service_delete_keeps_undo_available_when_save_fails(make_service: MakeService) -> None:
    store = _abc()
    service = make_service(store)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    store.fail_next_save(error)

    result = service.delete_task(B)
    service.undo()

    assert (result.save_error, _ids(service)) == (error, ["a", "b", "c"])


def test_service_undo_restores_deleted_task_at_previous_position(
    make_service: MakeService,
) -> None:
    store = _abc()
    service = make_service(store)
    original = service.plan
    service.delete_task(B)

    result = service.undo()

    assert (service.plan, store.saves[-1], result.changed, service.can_undo) == (
        original,
        service.plan,
        True,
        False,
    )


def test_service_undo_only_restores_last_delete(make_service: MakeService) -> None:
    store = FakeStore(make_plan(make_task("x"), make_task("y"), make_task("z")))
    service = make_service(store)
    service.delete_task(TaskId("x"))
    service.delete_task(TaskId("y"))

    first = service.undo()
    after_first = _ids(service)
    second = service.undo()

    assert (after_first, first.changed, second.changed, _ids(service)) == (
        ["y", "z"],
        True,
        False,
        ["y", "z"],
    )


def test_service_undo_with_nothing_deleted_does_nothing(make_service: MakeService) -> None:
    store = _abc()
    service = make_service(store)
    before = service.plan

    result = service.undo()

    assert (result.changed, store.save_calls, service.plan) == (False, 0, before)


def test_service_undo_after_delete_then_add_inserts_at_old_index(
    make_service: MakeService,
) -> None:
    store = FakeStore(make_plan(make_task("a"), make_task("b")))
    service = make_service(store)
    service.delete_task(A)
    service.add_task("D", make_slot(T(12), T(13)))

    service.undo()

    assert _ids(service) == ["a", "b", "t1"]


def test_service_clear_completed_removes_done_and_saves(make_service: MakeService) -> None:
    store = FakeStore(make_plan(make_task("a"), make_task("b", done=True), make_task("c")))
    service = make_service(store)

    result = service.clear_completed()

    assert (_ids(service), store.saves, result.changed, service.can_undo) == (
        ["a", "c"],
        [service.plan],
        True,
        True,
    )


def test_service_undo_after_clear_completed_restores_all_cleared(
    make_service: MakeService,
) -> None:
    store = FakeStore(
        make_plan(
            make_task("a"), make_task("b", done=True), make_task("c"), make_task("d", done=True)
        )
    )
    service = make_service(store)
    original = service.plan
    service.clear_completed()

    service.undo()

    assert (service.plan, store.saves[-1]) == (original, original)


def test_service_clear_completed_with_nothing_done_is_noop(make_service: MakeService) -> None:
    store = _abc()
    service = make_service(store)
    service.delete_task(B)
    saves = store.save_calls

    result = service.clear_completed()

    assert (result.changed, store.save_calls, service.can_undo) == (False, saves, True)
    service.undo()
    assert _ids(service) == ["a", "b", "c"]


def test_service_can_clear_completed_false_when_none_done(make_service: MakeService) -> None:
    service = make_service(_abc())
    before = service.can_clear_completed

    service.set_done(A, True)

    assert (before, service.can_clear_completed) == (False, True)


def test_service_second_delete_replaces_undo_slot_after_clear(make_service: MakeService) -> None:
    store = FakeStore(make_plan(make_task("p", done=True), make_task("q"), make_task("r")))
    service = make_service(store)
    service.clear_completed()
    service.delete_task(TaskId("q"))

    service.undo()

    assert _ids(service) == ["q", "r"]


def test_service_undo_twice_after_single_delete_restores_once(make_service: MakeService) -> None:
    service = make_service(_abc())
    service.delete_task(B)
    service.undo()

    second = service.undo()

    assert (second.changed, _ids(service)) == (False, ["a", "b", "c"])


def test_service_edit_title_does_not_clear_undo_slot(make_service: MakeService) -> None:
    service = make_service(_abc())
    service.delete_task(B)

    service.edit_title(A, "Renamed")
    service.undo()

    assert _ids(service) == ["a", "b", "c"]


def test_service_reschedule_does_not_clear_undo_slot(make_service: MakeService) -> None:
    service = make_service(_abc())
    service.delete_task(B)

    service.reschedule(A, make_slot(T(13), T(14)))
    service.undo()

    assert _ids(service) == ["a", "b", "c"]


def test_service_set_done_does_not_clear_undo_slot(make_service: MakeService) -> None:
    service = make_service(_abc())
    service.delete_task(B)

    service.set_done(A, True)

    assert service.can_undo
    service.undo()
    assert _ids(service) == ["a", "b", "c"]
