"""PlanService construction and startup."""

from datetime import time
from pathlib import Path

import pytest

from todo_qt.domain import Plan
from todo_qt.services import StoreWriteError

from .fakes import FakeStore, MakeService, RecordingStore, make_plan, make_task


def test_service_starts_empty_when_nothing_saved(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    service = make_service(fake_store)

    assert (service.plan.tasks, service.plan.day_start, service.startup_error) == (
        (),
        time(9, 0),
        None,
    )


def test_service_starts_with_saved_tasks_in_order_and_day_start(
    make_service: MakeService,
) -> None:
    saved = make_plan(
        make_task("a", "A"), make_task("b", "B"), make_task("c", "C"), day_start=time(8, 30)
    )

    service = make_service(FakeStore(saved))

    assert service.plan == saved


def test_service_starts_empty_on_corrupt_store_without_saving(
    make_service: MakeService,
) -> None:
    store = FakeStore.corrupt()

    service = make_service(store)

    assert (service.plan, service.startup_error, store.save_calls) == (
        Plan(),
        store.load_error,
        0,
    )


def test_service_does_not_save_during_construction(
    make_service: MakeService,
) -> None:
    store = RecordingStore(FakeStore(make_plan(make_task())))

    make_service(store)

    assert (store.saves, store.load_calls) == ([], 1)


def test_fake_store_load_returns_last_successful_save() -> None:
    old, new = make_plan(make_task("a")), make_plan(make_task("a"), make_task("b"))
    inner = FakeStore(old)
    store = RecordingStore(inner)

    store.save(new)
    assert store.load() == new

    inner.fail_next_save(StoreWriteError(Path("x"), "boom"))
    with pytest.raises(StoreWriteError):
        store.save(old)
    assert store.load() == new

    store.save(old)
    assert store.load() == old
