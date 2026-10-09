"""Tests for editing a task's title and slot through one controller command."""

from pathlib import Path

from todo_qt.domain import TaskId, TaskNotFoundError, TimeSlot
from todo_qt.services import StoreWriteError
from todo_qt.ui.controller import UiController
from todo_qt.ui.messages import (
    END_AFTER_START,
    TITLE_REQUIRED,
    message_for,
    save_failure_message,
)

from .fakes import FakeStore, MakeService, T


class Harness:
    """A controller over one task, with recorded notifications and changes."""

    def __init__(self, make_service: MakeService, store: FakeStore) -> None:
        self.service = make_service(store)
        self.service.add_task("Old", TimeSlot(T(9), T(10)))
        self.task_id = self.service.plan.tasks[0].id
        self.messages: list[str] = []
        self.changes = 0
        self.saves_before = store.save_calls
        self.store = store
        self.controller = UiController(self.service, self.messages.append, self._changed)

    def _changed(self) -> None:
        self.changes += 1

    def saves(self) -> int:
        return self.store.save_calls - self.saves_before

    def edit(self, title: str, start: int, end: int) -> bool:
        return self.controller.edit_task(self.task_id, title, T(start), T(end))


def test_ui_edit_task_applies_title_and_slot(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.edit(" New ", 11, 12)

    task = h.service.plan.tasks[0]
    assert (ok, task.title, task.slot, h.messages, h.changes, h.saves()) == (
        True,
        "New",
        TimeSlot(T(11), T(12)),
        [],
        1,
        2,
    )


def test_ui_edit_task_title_only_keeps_slot(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.edit("New", 9, 10)

    task = h.service.plan.tasks[0]
    assert (ok, task.title, task.slot, h.changes, h.saves()) == (
        True,
        "New",
        TimeSlot(T(9), T(10)),
        1,
        1,
    )


def test_ui_edit_task_slot_only_keeps_title(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.edit("Old", 13, 14)

    task = h.service.plan.tasks[0]
    assert (ok, task.title, task.slot, h.changes, h.saves()) == (
        True,
        "Old",
        TimeSlot(T(13), T(14)),
        1,
        1,
    )


def test_ui_edit_task_without_changes_does_not_save_or_refresh(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.edit("Old", 9, 10)

    assert (ok, h.changes, h.saves()) == (True, 0, 0)


def test_ui_edit_task_blank_title_is_rejected_without_changes(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.edit("  ", 11, 12)

    assert (ok, h.messages, h.service.plan.tasks[0].slot.start) == (False, [TITLE_REQUIRED], T(9))


def test_ui_edit_task_end_not_after_start_leaves_title_unchanged(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.edit("New", 12, 11)

    assert (ok, h.messages, h.service.plan.tasks[0].title) == (False, [END_AFTER_START], "Old")


def test_ui_edit_task_both_invalid_reports_title_message(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.edit("", 12, 11)

    assert (ok, h.messages) == (False, [TITLE_REQUIRED])


def test_ui_edit_task_unknown_id_reports_not_found(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    ok = h.controller.edit_task(TaskId("nope"), "New", T(11), T(12))

    assert (ok, h.messages) == (False, [message_for(TaskNotFoundError(TaskId("nope")))])


def test_ui_edit_task_title_step_save_failure_reports_once_and_applies_both(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    fake_store.fail_next_save(error)

    ok = h.edit("New", 11, 12)

    task = h.service.plan.tasks[0]
    assert (ok, h.messages, h.changes, task.title, task.slot) == (
        True,
        [save_failure_message(error)],
        1,
        "New",
        TimeSlot(T(11), T(12)),
    )


def test_ui_edit_task_slot_step_save_failure_reports_and_keeps_change(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    fake_store.fail_next_save(error)

    ok = h.edit("Old", 11, 12)

    assert (ok, h.messages, h.changes, h.service.plan.tasks[0].slot) == (
        True,
        [save_failure_message(error)],
        1,
        TimeSlot(T(11), T(12)),
    )


def test_ui_edit_task_slot_step_save_failure_after_title_saved_is_reported(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)
    h.edit("New", 9, 10)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    fake_store.fail_next_save(error)

    ok = h.edit("Newer", 11, 12)

    assert (ok, h.messages) == (True, [save_failure_message(error)])
