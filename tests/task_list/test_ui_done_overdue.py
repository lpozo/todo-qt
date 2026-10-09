"""UI done and overdue display: strike-out, highlight, toggle, and timer refresh."""

from datetime import timedelta

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QBrush, QFont
from pytestqt.qtbot import QtBot

from todo_qt.ui.convert import to_qdatetime
from todo_qt.ui.main_window import OVERDUE_REFRESH_MS, MainWindow
from todo_qt.ui.task_model import OVERDUE_ROLE

from .fakes import MakeService, MutableClock, T


def _add_task(window: MainWindow, start_hour: int, end_hour: int) -> QModelIndex:
    window.add_button.click()
    form = window.add_form
    form.title_edit.setText("Task")
    form.start_edit.setDateTime(to_qdatetime(T(start_hour)))
    form.end_edit.setDateTime(to_qdatetime(T(end_hour)))
    form.confirm_button.click()
    return window.model.index(window.model.rowCount() - 1)


def _window(qtbot: QtBot, make_service: MakeService) -> MainWindow:
    window = MainWindow(make_service())
    qtbot.addWidget(window)
    return window


def _struck(index: QModelIndex) -> bool:
    font = index.data(Qt.ItemDataRole.FontRole)
    return isinstance(font, QFont) and font.strikeOut()


def _highlighted(index: QModelIndex) -> bool:
    return isinstance(index.data(Qt.ItemDataRole.BackgroundRole), QBrush)


def test_ui_add_past_task_is_highlighted_overdue(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)

    index = _add_task(window, 7, 8)

    assert (index.data(OVERDUE_ROLE), _highlighted(index)) == (True, True)


def test_ui_toggle_done_strikes_through_and_clears_overdue(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    index = _add_task(window, 7, 8)

    window.model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)

    index = window.model.index(0)
    assert (_struck(index), index.data(OVERDUE_ROLE), _highlighted(index), index.row()) == (
        True,
        False,
        False,
        0,
    )


def test_ui_toggle_undone_restores_overdue_highlight(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    index = _add_task(window, 7, 8)
    window.model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)

    window.model.setData(
        window.model.index(0), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole
    )

    index = window.model.index(0)
    assert (_struck(index), index.data(OVERDUE_ROLE), _highlighted(index)) == (False, True, True)


def test_ui_overdue_highlight_appears_without_user_action(
    qtbot: QtBot, make_service: MakeService, clock: MutableClock
) -> None:
    window = _window(qtbot, make_service)
    index = _add_task(window, 11, 12)
    assert index.data(OVERDUE_ROLE) is False

    assert window.overdue_timer.interval() == OVERDUE_REFRESH_MS == 15_000
    clock.advance(timedelta(hours=3))
    with qtbot.waitSignal(window.model.dataChanged, timeout=5000):
        window.overdue_timer.timeout.emit()

    assert (window.model.index(0).data(OVERDUE_ROLE), _highlighted(window.model.index(0))) == (
        True,
        True,
    )


def test_ui_overdue_timer_is_active_and_refreshes_at_most_every_30_seconds(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    assert (window.overdue_timer.isActive(), window.overdue_timer.interval() <= 30_000) == (
        True,
        True,
    )


def test_ui_refresh_overdue_without_change_emits_nothing(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    _add_task(window, 7, 8)

    with qtbot.assertNotEmitted(window.model.dataChanged):
        window.refresh_overdue()


def test_ui_refresh_overdue_on_empty_model_is_safe(
    qtbot: QtBot, make_service: MakeService, clock: MutableClock
) -> None:
    window = _window(qtbot, make_service)

    with qtbot.assertNotEmitted(window.model.dataChanged):
        window.refresh_overdue()

    assert window.model.rowCount() == 0


def test_ui_set_data_accepts_int_check_states(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    _add_task(window, 7, 8)

    window.model.setData(window.model.index(0), 2, Qt.ItemDataRole.CheckStateRole)
    done = window.model.index(0).data(Qt.ItemDataRole.CheckStateRole)
    window.model.setData(window.model.index(0), 0, Qt.ItemDataRole.CheckStateRole)
    undone = window.model.index(0).data(Qt.ItemDataRole.CheckStateRole)

    assert (done, undone) == (Qt.CheckState.Checked, Qt.CheckState.Unchecked)


def test_ui_rows_are_user_checkable(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    index = _add_task(window, 7, 8)

    assert Qt.ItemFlag.ItemIsUserCheckable in window.model.flags(index)
