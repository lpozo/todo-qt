"""UI stale state: an open edit form keeps re-chains; later commands clear old messages."""

from collections.abc import Callable
from datetime import time
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QModelIndex, Qt
from pytestqt.qtbot import QtBot

from todo_qt.domain import TaskId
from todo_qt.services import ChangeResult, StoreWriteError
from todo_qt.ui.controller import UiController
from todo_qt.ui.convert import to_qdatetime
from todo_qt.ui.main_window import MainWindow

from .fakes import FakeStore, MakeService, T, make_plan, make_slot, make_task

_ROOT = QModelIndex()


def _store() -> FakeStore:
    return FakeStore(
        make_plan(
            make_task("a", "A", make_slot(T(10), T(11))),
            make_task("b", "B", make_slot(T(11), T(12))),
            day_start=time(9, 0),
        )
    )


def _chained_store() -> FakeStore:
    return FakeStore(
        make_plan(
            make_task("a", "A", make_slot(T(9), T(10))),
            make_task("b", "B", make_slot(T(10), T(11))),
            day_start=time(9, 0),
        )
    )


def _window(qtbot: QtBot, make_service: MakeService, store: FakeStore) -> MainWindow:
    window = MainWindow(make_service(store))
    qtbot.addWidget(window)
    return window


def _rows(window: MainWindow) -> list[tuple[str, object, object]]:
    return [(t.title, t.slot.start, t.slot.end) for t in window._service.plan.tasks]


def _set_day_start(window: MainWindow, hour: int) -> None:
    window._service.set_day_start(time(hour, 0))
    window.refresh()


def _drag(window: MainWindow, row: int, drop_row: int) -> None:
    data = window.model.mimeData([window.model.index(row)])
    window.model.dropMimeData(data, Qt.DropAction.MoveAction, drop_row, 0, _ROOT)


def test_ui_confirming_edit_after_rechain_keeps_new_times(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _store())
    window.open_edit_form(window.model.index(0))
    _set_day_start(window, 8)

    window.add_form.title_edit.setText("A2")
    window.add_form.confirm()

    assert _rows(window) == [("A2", T(8), T(9)), ("B", T(9), T(10))]


def test_ui_changing_times_after_rechain_applies_the_users_times(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _store())
    window.open_edit_form(window.model.index(0))
    _set_day_start(window, 8)

    window.add_form.start_edit.setDateTime(to_qdatetime(T(13)))
    window.add_form.end_edit.setDateTime(to_qdatetime(T(14)))
    window.add_form.confirm()

    a = next(t for t in window._service.plan.tasks if t.id == "a")
    assert (a.slot.start, a.slot.end) == (T(13), T(14))


def test_ui_confirming_edit_after_drag_move_keeps_new_times(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.open_edit_form(window.model.index(0))
    _drag(window, 1, 0)

    window.add_form.title_edit.setText("A2")
    window.add_form.confirm()

    assert _rows(window) == [("B", T(9), T(10)), ("A2", T(10), T(11))]


def test_ui_changing_times_after_drag_move_applies_the_users_times(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.open_edit_form(window.model.index(0))
    _drag(window, 1, 0)

    window.add_form.start_edit.setDateTime(to_qdatetime(T(15)))
    window.add_form.end_edit.setDateTime(to_qdatetime(T(16)))
    window.add_form.confirm()

    a = next(t for t in window._service.plan.tasks if t.id == "a")
    assert (a.slot.start, a.slot.end) == (T(15), T(16))


_FAILURE = StoreWriteError(Path("tasks.json"), "disk full")


def _toggle_done(window: MainWindow) -> None:
    window.model.setData(
        window.model.index(0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole
    )


def _undo_after_delete(window: MainWindow) -> None:
    window.list_view.setCurrentIndex(window.model.index(1))
    window.delete_button.click()
    window.message_label.setText("stale")
    window.undo_action.trigger()


def _clear_completed(window: MainWindow) -> None:
    window._service.set_done(window._service.plan.tasks[0].id, True)
    window.refresh()
    window.message_label.setText("stale")
    window.clear_completed_button.click()


def _drag_move(window: MainWindow) -> None:
    _drag(window, 1, 0)


@pytest.mark.parametrize(
    "second_command",
    [_toggle_done, _undo_after_delete, _clear_completed, _drag_move],
    ids=["toggle_done", "undo", "clear_completed", "drag_move"],
)
def test_ui_successful_command_clears_stale_save_failure_message(
    qtbot: QtBot,
    make_service: MakeService,
    fake_store: FakeStore,
    second_command: Callable[[MainWindow], None],
) -> None:
    fake_store.plan = _store().plan
    window = _window(qtbot, make_service, fake_store)
    fake_store.fail_next_save(_FAILURE)
    window.controller.set_day_start(time(8, 0))
    assert window.message_label.text() != ""
    window.message_label.setText("Could not save your changes: may be lost")

    second_command(window)

    assert window.message_label.text() == ""


def test_ui_own_position_drop_keeps_the_message(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service, _store())
    window.message_label.setText("stale")

    _drag(window, 0, 0)

    assert window.message_label.text() == "stale"


def test_ui_command_error_still_shows_after_clearing(
    qtbot: QtBot, make_service: MakeService, fake_store: FakeStore
) -> None:
    fake_store.plan = _store().plan
    window = _window(qtbot, make_service, fake_store)
    window.message_label.setText("stale")
    fake_store.fail_next_save(_FAILURE)

    _toggle_done(window)

    assert "Could not save" in window.message_label.text()


def _task_a(window: MainWindow) -> tuple[object, object]:
    a = next(t for t in window._service.plan.tasks if t.id == "a")
    return (a.slot.start, a.slot.end)


def test_ui_changing_only_the_end_after_rechain_keeps_the_new_start(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.open_edit_form(window.model.index(0))
    _set_day_start(window, 8)

    window.add_form.end_edit.setDateTime(to_qdatetime(T(10, 30)))
    window.add_form.confirm()

    assert _task_a(window) == (T(8), T(10, 30))


def test_ui_changing_only_the_start_after_rechain_keeps_the_new_end(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.open_edit_form(window.model.index(0))
    _set_day_start(window, 8)

    window.add_form.start_edit.setDateTime(to_qdatetime(T(8, 30)))
    window.add_form.confirm()

    assert _task_a(window) == (T(8, 30), T(9))


def test_ui_resetting_times_to_the_opened_values_keeps_the_rechain(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.open_edit_form(window.model.index(0))
    _set_day_start(window, 8)
    window.add_form.start_edit.setDateTime(to_qdatetime(T(13)))
    window.add_form.start_edit.setDateTime(to_qdatetime(T(9)))

    window.add_form.confirm()

    assert _rows(window) == [("A", T(8), T(9)), ("B", T(9), T(10))]


def test_ui_confirming_edit_after_undo_rechain_keeps_new_times(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.list_view.setCurrentIndex(window.model.index(0))
    window.delete_button.click()  # B alone, re-chained to 09-10
    window.open_edit_form(window.model.index(0))
    _set_day_start(window, 8)
    window.undo_action.trigger()  # A comes back; B keeps its 08-09 slot

    window.add_form.title_edit.setText("B2")
    window.add_form.confirm()

    assert ("B2", T(8), T(9)) in _rows(window)


def test_ui_undo_with_nothing_to_undo_keeps_the_message(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.message_label.setText("stale")

    window.controller.undo()  # the action is disabled; call the command directly

    assert window.message_label.text() == "stale"


@pytest.mark.parametrize("action", [Qt.DropAction.CopyAction, Qt.DropAction.IgnoreAction])
def test_ui_drop_with_wrong_action_keeps_the_message(
    qtbot: QtBot, make_service: MakeService, action: Qt.DropAction
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.message_label.setText("stale")
    data = window.model.mimeData([window.model.index(1)])

    window.model.dropMimeData(data, action, 0, 0, _ROOT)

    assert window.message_label.text() == "stale"


def test_ui_drop_with_foreign_payload_keeps_the_message(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.message_label.setText("stale")

    window.model.dropMimeData(QMimeData(), Qt.DropAction.MoveAction, 0, 0, _ROOT)

    assert window.message_label.text() == "stale"


def test_ui_day_start_no_op_keeps_the_message(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service, _chained_store())
    window.message_label.setText("stale")

    window.day_start_edit.editingFinished.emit()

    assert window.message_label.text() == "stale"


class _Recorder:
    """A controller over a one-task plan that logs clears, notices and refreshes."""

    def __init__(self, make_service: MakeService) -> None:
        self.log: list[str] = []
        self.service = make_service(_chained_store())
        self.controller = UiController(
            self.service,
            lambda m: self.log.append(f"notify:{m}"),
            lambda: self.log.append("change"),
            lambda: self.log.append("clear"),
        )


def test_ui_controller_clears_the_message_before_the_command(make_service: MakeService) -> None:
    rec = _Recorder(make_service)

    rec.controller.set_done(TaskId("a"), True)

    assert rec.log == ["clear", "change"]


def test_ui_controller_error_after_clear_still_reaches_the_notifier(
    make_service: MakeService,
) -> None:
    rec = _Recorder(make_service)

    rec.controller.set_done(TaskId("missing"), True)

    assert rec.log[0] == "clear"
    assert rec.log[1].startswith("notify:")


def test_ui_controller_run_with_clear_false_skips_the_clear(make_service: MakeService) -> None:
    rec = _Recorder(make_service)

    rec.controller._run(lambda: ChangeResult(rec.service.plan, changed=False), clear=False)

    assert rec.log == []


def test_ui_controller_edit_task_with_all_parts_none_is_a_no_op(make_service: MakeService) -> None:
    rec = _Recorder(make_service)
    before = rec.service.plan

    accepted = rec.controller.edit_task(TaskId("a"), None, None, None)

    assert (accepted, rec.service.plan, rec.log) == (True, before, ["clear"])
