"""Tests for adding tasks through the UI controller."""

from pathlib import Path

from todo_qt.domain import TaskId
from todo_qt.services import StoreWriteError
from todo_qt.ui.controller import UiController
from todo_qt.ui.messages import END_AFTER_START, TITLE_REQUIRED, save_failure_message

from .fakes import FakeStore, MakeService, T


class Harness:
    """A controller with recorded notifications and change callbacks."""

    def __init__(self, make_service: MakeService, store: FakeStore) -> None:
        self.service = make_service(store)
        self.messages: list[str] = []
        self.changes = 0
        self.controller = UiController(self.service, self.messages.append, self._changed)

    def _changed(self) -> None:
        self.changes += 1


def test_ui_add_blank_title_shows_title_required(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    accepted = h.controller.add_task("   ", T(9), T(10))

    assert (accepted, h.messages, h.service.plan.tasks) == (False, [TITLE_REQUIRED], ())


def test_ui_add_end_not_after_start_shows_end_after_start_message(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    accepted = h.controller.add_task("Write", T(10), T(10))

    assert (accepted, h.messages, h.service.plan.tasks) == (False, [END_AFTER_START], ())


def test_ui_add_blank_title_and_bad_slot_shows_only_title_message(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    h.controller.add_task("", T(10), T(9))

    assert h.messages == [TITLE_REQUIRED]


def test_ui_add_valid_task_is_added_trimmed_and_notifies_change(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    accepted = h.controller.add_task("  Write  ", T(9), T(10))

    task = h.service.plan.tasks[0]
    assert (accepted, task.title, task.id, h.messages, h.changes) == (
        True,
        "Write",
        TaskId("t1"),
        [],
        1,
    )


def test_ui_add_rejection_does_not_call_on_change(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    h = Harness(make_service, fake_store)

    h.controller.add_task("", T(9), T(10))

    assert h.changes == 0


def test_ui_add_save_failure_is_reported_and_task_is_kept(
    make_service: MakeService, fake_store: FakeStore
) -> None:
    error = StoreWriteError(Path("tasks.json"), "disk full")
    fake_store.fail_next_save(error)
    h = Harness(make_service, fake_store)

    accepted = h.controller.add_task("Write", T(9), T(10))

    assert (accepted, h.messages, len(h.service.plan.tasks), h.changes) == (
        True,
        [save_failure_message(error)],
        1,
        1,
    )
