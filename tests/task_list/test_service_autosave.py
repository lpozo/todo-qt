"""Auto-save and restart behavior across all commands."""

from datetime import time
from pathlib import Path

from todo_qt.domain import TaskId
from todo_qt.persistence import JsonPlanStore
from todo_qt.services import PlanService

from .fakes import (
    IdCounter,
    MakeService,
    MutableClock,
    RecordingStore,
    T,
    make_slot,
)


def test_service_saves_after_every_kind_of_change(
    make_service: MakeService, recording_store: RecordingStore
) -> None:
    service = make_service(recording_store)
    a, b = TaskId("t1"), TaskId("t2")
    commands = [
        lambda: service.add_task("A", make_slot(T(9), T(10))),
        lambda: service.add_task("B", make_slot(T(11), T(12))),
        lambda: service.edit_title(a, "A2"),
        lambda: service.reschedule(a, make_slot(T(9), T(10, 30))),
        lambda: service.set_done(a, True),
        lambda: service.set_done(a, False),
        lambda: service.move_task(b, 0),
        lambda: service.delete_task(a),
        lambda: service.set_done(b, True),
        lambda: service.clear_completed(),
        lambda: service.undo(),
        lambda: service.set_day_start(time(8, 0)),
    ]
    expected = []

    for command in commands:
        assert command().changed
        expected.append(service.plan)

    assert recording_store.saves == expected


def test_service_restart_after_kill_shows_last_change(
    tmp_path: Path, clock: MutableClock, new_id: IdCounter
) -> None:
    service = PlanService(JsonPlanStore(tmp_path), clock, new_id)
    service.add_task("A", make_slot(T(9), T(10)))
    service.set_done(TaskId("t1"), True)
    last = service.plan
    del service

    restarted = PlanService(JsonPlanStore(tmp_path), clock, IdCounter("u"))

    assert restarted.plan == last


def test_service_restart_preserves_order_titles_times_done_flags(
    tmp_path: Path, clock: MutableClock, new_id: IdCounter
) -> None:
    service = PlanService(JsonPlanStore(tmp_path), clock, new_id)
    service.add_task("A", make_slot(T(9), T(10)))
    service.add_task("B", make_slot(T(10), T(11)))
    service.add_task("C", make_slot(T(12), T(12, 30)))
    service.set_done(TaskId("t2"), True)
    service.move_task(TaskId("t3"), 1)

    restarted = PlanService(JsonPlanStore(tmp_path), clock, IdCounter("u"))

    assert restarted.plan == service.plan
