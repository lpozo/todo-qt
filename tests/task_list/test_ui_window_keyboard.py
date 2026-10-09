"""UI keyboard handling: Enter confirms the form, Delete removes the selected task."""

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QKeySequence
from pytestqt.qtbot import QtBot

from todo_qt.domain import TimeSlot
from todo_qt.ui.main_window import MainWindow, _delete_shortcuts

from .fakes import MakeService, T


def _window(qtbot: QtBot, make_service: MakeService) -> MainWindow:
    service = make_service()
    service.add_task("First", TimeSlot(T(9), T(10)))
    service.add_task("Second", TimeSlot(T(11), T(12)))
    service.add_task("Third", TimeSlot(T(13), T(14)))
    window = MainWindow(service)
    qtbot.addWidget(window)
    return window


def _titles(window: MainWindow) -> list[str]:
    rows = range(window.model.rowCount())
    texts = (window.model.index(row).data(Qt.ItemDataRole.DisplayRole) for row in rows)
    return [str(text).split("\n")[0] for text in texts]


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_ui_enter_in_add_form_confirms_task(
    qtbot: QtBot, make_service: MakeService, key: Qt.Key
) -> None:
    window = _window(qtbot, make_service)
    window.open_add_form()
    window.add_form.title_edit.setText("X")

    qtbot.keyClick(window.add_form.title_edit, key)

    assert "X" in _titles(window)
    assert not window.add_form.isVisible()


def test_ui_enter_with_blank_title_adds_nothing_and_shows_message(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.open_add_form()

    qtbot.keyClick(window.add_form.title_edit, Qt.Key.Key_Return)

    assert _titles(window) == ["First", "Second", "Third"]
    assert window.message_label.text() == "A title is required."


def test_ui_enter_in_edit_mode_saves_the_edit(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(1))
    window.add_form.title_edit.setText("Renamed")

    qtbot.keyClick(window.add_form.title_edit, Qt.Key.Key_Return)

    assert _titles(window) == ["First", "Renamed", "Third"]


def test_ui_delete_key_deletes_selected_task_and_is_undoable(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.list_view.setCurrentIndex(window.model.index(1))

    # Gap: window activation is unreliable offscreen once other windows exist, so a real
    # Delete key click cannot dispatch the shortcut; the wiring is covered by the scope
    # test below and the action is triggered directly here.
    window.delete_action.trigger()
    assert _titles(window) == ["First", "Third"]

    window.undo_action.trigger()
    assert _titles(window) == ["First", "Second", "Third"]


def test_ui_delete_key_without_selection_does_nothing(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    # A focused-but-unselected current row must not count as a selection.
    window.list_view.selectionModel().setCurrentIndex(
        window.model.index(0), QItemSelectionModel.SelectionFlag.NoUpdate
    )

    window.delete_action.trigger()

    assert _titles(window) == ["First", "Second", "Third"]
    assert window.message_label.text() == ""


def test_ui_delete_and_backspace_in_title_field_edit_text_only(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.list_view.setCurrentIndex(window.model.index(1))
    window.open_add_form()
    # Note: key clicks go straight to the field; this does not exercise the shortcut map.
    window.add_form.title_edit.setText("abc")

    qtbot.keyClick(window.add_form.title_edit, Qt.Key.Key_Backspace)
    window.add_form.title_edit.setCursorPosition(0)
    qtbot.keyClick(window.add_form.title_edit, Qt.Key.Key_Delete)

    assert window.add_form.title_edit.text() == "b"
    assert _titles(window) == ["First", "Second", "Third"]


def test_ui_delete_shortcut_is_scoped_to_the_list_view(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    actions = [
        a
        for a in window.list_view.actions()
        if QKeySequence(QKeySequence.StandardKey.Delete) in a.shortcuts()
    ]

    assert len(actions) == 1
    assert actions[0].shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut


def test_ui_delete_action_is_not_window_level_and_not_over_the_form_or_day_start(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    assert window.delete_action in window.list_view.actions()
    assert window.delete_action not in window.actions()
    assert not window.list_view.isAncestorOf(window.add_form)
    assert not window.list_view.isAncestorOf(window.day_start_edit)


def test_ui_delete_shortcuts_are_delete_only_on_linux() -> None:
    assert _delete_shortcuts("linux") == [QKeySequence(Qt.Key.Key_Delete)]


def test_ui_delete_shortcuts_add_backspace_on_macos() -> None:
    assert _delete_shortcuts("darwin") == [
        QKeySequence(Qt.Key.Key_Delete),
        QKeySequence(Qt.Key.Key_Backspace),
    ]


def test_ui_delete_key_deletes_the_selected_row_not_the_current_one(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.list_view.setCurrentIndex(window.model.index(0))
    window.list_view.selectionModel().setCurrentIndex(
        window.model.index(2), QItemSelectionModel.SelectionFlag.NoUpdate
    )

    window.delete_action.trigger()

    assert _titles(window) == ["Second", "Third"]


def test_ui_second_delete_key_does_nothing_because_the_reset_clears_selection(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.list_view.setCurrentIndex(window.model.index(0))

    window.delete_action.trigger()
    window.delete_action.trigger()

    assert _titles(window) == ["Second", "Third"]
