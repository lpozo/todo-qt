"""A later successful save persists earlier unsaved changes."""

from pathlib import Path

from todo_qt.services import StoreWriteError

from .fakes import FakeStore, MakeService, make_slot


def test_service_next_successful_save_persists_earlier_unsaved_change(
    make_service: MakeService,
) -> None:
    store = FakeStore()
    service = make_service(store)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    store.fail_next_save(error)
    added = service.add_task("X", make_slot())
    assert added.task_id is not None

    result = service.set_done(added.task_id, True)

    assert (
        added.save_error,
        added.changed,
        result.save_error,
        store.plan,
        store.save_calls,
    ) == (error, True, None, service.plan, 2)
    assert [(t.title, t.done) for t in service.plan.tasks] == [("X", True)]
