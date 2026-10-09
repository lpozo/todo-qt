"""Tests for editing, rescheduling, and completing tasks through the UI controller."""

from todo_qt.domain import TaskId
from todo_qt.ui.controller import UiController
from todo_qt.ui.messages import END_AFTER_START, TITLE_REQUIRED

from .fakes import FakeStore, MakeService, T, make_plan, make_task

A = TaskId("a")


class Harness:
    """A controller over one task, with recorded notifications and changes."""

    def __init__(self, make_service: MakeService) -> None:
        self.service = make_service(FakeStore(make_plan(make_task("a", "Buy milk"))))
        self.messages: list[str] = []
        self.changes = 0
        self.controller = UiController(self.service, self.messages.append, self._changed)

    def _changed(self) -> None:
        self.changes += 1


def test_ui_edit_title_blank_keeps_original(make_service: MakeService) -> None:
    h = Harness(make_service)

    accepted = h.controller.edit_title(A, "  ")

    assert (accepted, h.service.plan.tasks[0].title, h.messages, h.changes) == (
        False,
        "Buy milk",
        [TITLE_REQUIRED],
        0,
    )


def test_ui_edit_title_valid_is_trimmed_and_notifies_change(
    make_service: MakeService,
) -> None:
    h = Harness(make_service)

    accepted = h.controller.edit_title(A, "  Buy oat milk ")

    assert (accepted, h.service.plan.tasks[0].title, h.messages, h.changes) == (
        True,
        "Buy oat milk",
        [],
        1,
    )


def test_ui_reschedule_end_not_after_start_keeps_original_times(
    make_service: MakeService,
) -> None:
    h = Harness(make_service)
    before = h.service.plan.tasks[0].slot

    accepted = h.controller.reschedule(A, T(9), T(8))

    assert (accepted, h.service.plan.tasks[0].slot, h.messages, h.changes) == (
        False,
        before,
        [END_AFTER_START],
        0,
    )


def test_ui_reschedule_valid_slot_updates_times_and_notifies_change(
    make_service: MakeService,
) -> None:
    h = Harness(make_service)

    accepted = h.controller.reschedule(A, T(11), T(12))

    slot = h.service.plan.tasks[0].slot
    assert (accepted, slot.start, slot.end, h.changes) == (True, T(11), T(12), 1)


def test_ui_set_done_marks_task_done_and_notifies_change(
    make_service: MakeService,
) -> None:
    h = Harness(make_service)

    accepted = h.controller.set_done(A, True)

    assert (accepted, h.service.plan.tasks[0].done, h.changes) == (True, True, 1)


def test_ui_set_done_unchanged_is_accepted_without_change_notification(
    make_service: MakeService,
) -> None:
    h = Harness(make_service)

    accepted = h.controller.set_done(A, False)

    assert (accepted, h.changes, h.messages) == (True, 0, [])
