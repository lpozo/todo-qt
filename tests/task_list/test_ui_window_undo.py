"""UI delete, undo, and clear completed."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from pytestqt.qtbot import QtBot

from todo_qt.domain import TimeSlot
from todo_qt.services import StoreWriteError
from todo_qt.ui.main_window import MainWindow
from todo_qt.ui.messages import save_failure_message

from .fakes import FakeStore, MakeService, T


def _slot(start: int, end: int) -> TimeSlot:
    return TimeSlot(T(start), T(end))


def _window(qtbot: QtBot, make_service: MakeService, done: tuple[int, ...] = ()) -> MainWindow:
    service = make_service()
    service.add_task("First", _slot(9, 10))
    service.add_task("Second", _slot(11, 12))
    service.add_task("Third", _slot(13, 14))
    for row in done:
        service.set_done(service.plan.tasks[row].id, True)
    window = MainWindow(service)
    qtbot.addWidget(window)
    return window


def _titles(window: MainWindow) -> list[str]:
    rows = range(window.model.rowCount())
    texts = (window.model.index(row).data(Qt.ItemDataRole.DisplayRole) for row in rows)
    return [str(text).split("\n")[0] for text in texts]


def test_ui_ctrl_z_restores_last_deleted_task(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    window.list_view.setCurrentIndex(window.model.index(1))
    window.delete_button.click()
    assert _titles(window) == ["First", "Third"]

    assert window.undo_action in window.actions()
    assert window.undo_action.shortcutContext() == Qt.ShortcutContext.WindowShortcut
    assert window.undo_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Undo)
    window.undo_action.trigger()

    assert _titles(window) == ["First", "Second", "Third"]
    assert window.model.rowCount() == 3


def test_ui_undo_with_nothing_deleted_changes_nothing(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    window.undo_action.trigger()

    assert _titles(window) == ["First", "Second", "Third"]
    assert window.message_label.text() == ""


def test_ui_delete_without_selection_does_nothing(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)

    window.delete_button.click()

    assert _titles(window) == ["First", "Second", "Third"]


def test_ui_deleting_task_being_edited_closes_the_form(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.list_view.setCurrentIndex(window.model.index(0))
    window.open_edit_form(window.model.index(0))
    window.show()

    window.delete_button.click()

    assert (window.add_form.isVisible(), window._editing_id) == (False, None)


def test_ui_clear_completed_disabled_when_nothing_done(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    assert not window.clear_completed_button.isEnabled()


def test_ui_clear_completed_removes_done_rows_and_ctrl_z_restores_them(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, done=(0, 2))
    assert window.clear_completed_button.isEnabled()

    window.clear_completed_button.click()
    assert _titles(window) == ["Second"]
    assert not window.clear_completed_button.isEnabled()

    window.undo_action.trigger()

    assert _titles(window) == ["First", "Second", "Third"]
    assert window.clear_completed_button.isEnabled()


def test_ui_enabled_states_follow_done_toggles(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    index = window.model.index(0)

    window.model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    enabled_after_check = window.clear_completed_button.isEnabled()
    window.model.setData(index, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)

    assert (enabled_after_check, window.clear_completed_button.isEnabled()) == (True, False)


def test_ui_undo_controls_follow_the_undo_slot(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    initial = (window.undo_action.isEnabled(), window.undo_button.isEnabled())
    window.list_view.setCurrentIndex(window.model.index(0))
    window.delete_button.click()
    after_delete = (window.undo_action.isEnabled(), window.undo_button.isEnabled())

    window.undo_button.click()

    after_undo = (window.undo_action.isEnabled(), window.undo_button.isEnabled())
    assert (initial, after_delete, after_undo) == ((False, False), (True, True), (False, False))


def test_ui_delete_save_failure_shows_message_and_keeps_undo(
    qtbot: QtBot, make_service: MakeService, fake_store: FakeStore
) -> None:
    window = _window(qtbot, make_service)
    error = StoreWriteError(Path("tasks.json"), "disk full")
    fake_store.fail_next_save(error)
    window.list_view.setCurrentIndex(window.model.index(0))

    window.delete_button.click()

    assert (window.message_label.text(), _titles(window), window.undo_action.isEnabled()) == (
        save_failure_message(error),
        ["Second", "Third"],
        True,
    )


def test_ui_deleting_another_task_keeps_the_edit_form_open(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.show()
    window.open_edit_form(window.model.index(0))
    window.add_form.title_edit.setText("My draft")
    window.list_view.setCurrentIndex(window.model.index(2))

    window.delete_button.click()

    assert (window.add_form.isVisible(), window.add_form.title_edit.text()) == (True, "My draft")
    assert window._editing_id is not None


# Not covered: real Ctrl+Z key presses. Under the offscreen platform QTest.keyClick does not
# fire window shortcuts (10/10 runs failed), so the wiring is pinned structurally above
# (action in window.actions(), WindowShortcut context, StandardKey.Undo). With focus in the
# form's QLineEdit, Qt's ShortcutOverride lets the editor keep its own Ctrl+Z; untested here.
