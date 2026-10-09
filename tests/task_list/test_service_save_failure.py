"""Auto-save failure handling."""

from pathlib import Path

import pytest

from todo_qt.services import PlanSnapshot, StoreWriteError

from .fakes import FakeStore, MakeService, make_slot


class ExplodingStore:
    """A store whose save raises a non-write error."""

    def load(self) -> PlanSnapshot | None:
        return None

    def save(self, snapshot: PlanSnapshot) -> None:
        raise RuntimeError("boom")


def test_service_keeps_change_in_memory_when_save_fails(make_service: MakeService) -> None:
    error = StoreWriteError(Path("tasks.json"), "disk full")
    service = make_service(FakeStore(save_error=error))

    result = service.add_task("X", make_slot())

    assert (
        [task.title for task in service.plan.tasks],
        result.save_error,
        result.changed,
    ) == (["X"], error, True)


def test_service_non_write_store_errors_propagate(make_service: MakeService) -> None:
    service = make_service(ExplodingStore())

    with pytest.raises(RuntimeError):
        service.add_task("X", make_slot())
