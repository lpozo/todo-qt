"""UI add form: pre-fill, add, and error messages."""

from datetime import datetime

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from todo_qt.ui.convert import to_datetime, to_qdatetime
from todo_qt.ui.main_window import MainWindow
from todo_qt.ui.task_model import DONE_ROLE

from .fakes import MakeService, MutableClock, T


def _open(qtbot: QtBot, make_service: MakeService) -> MainWindow:
    window = MainWindow(make_service())
    qtbot.addWidget(window)
    window.add_button.click()
    return window


def test_ui_add_form_is_prefilled_with_next_full_hour(
    qtbot: QtBot, make_service: MakeService, clock: MutableClock
) -> None:
    clock.now = T(14, 20)
    window = _open(qtbot, make_service)

    form = window.add_form
    assert (form.start_edit.dateTime(), form.end_edit.dateTime()) == (
        to_qdatetime(T(15)),
        to_qdatetime(T(15, 30)),
    )


def test_ui_add_valid_task_appears_at_bottom(qtbot: QtBot, make_service: MakeService) -> None:
    window = _open(qtbot, make_service)
    window.add_form.title_edit.setText("Buy milk")

    window.add_form.confirm_button.click()

    last = window.model.index(window.model.rowCount() - 1)
    assert (last.data(Qt.ItemDataRole.DisplayRole).split("\n")[0], last.data(DONE_ROLE)) == (
        "Buy milk",
        False,
    )


def test_ui_add_blank_title_shows_message_in_label(qtbot: QtBot, make_service: MakeService) -> None:
    window = _open(qtbot, make_service)
    window.add_form.title_edit.setText("  ")

    window.add_form.confirm_button.click()

    assert (window.model.rowCount(), window.message_label.text()) == (
        0,
        "A title is required.",
    )


def test_ui_add_uses_injected_notifier(qtbot: QtBot, make_service: MakeService) -> None:
    seen: list[str] = []
    window = MainWindow(make_service(), notifier=seen.append)
    qtbot.addWidget(window)
    window.add_button.click()

    window.add_form.confirm_button.click()

    assert seen == ["A title is required."]


def test_ui_add_rejected_keeps_form_open_with_user_input(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _open(qtbot, make_service)
    form = window.add_form
    form.title_edit.setText("  ")
    form.start_edit.setDateTime(to_qdatetime(T(11)))
    form.end_edit.setDateTime(to_qdatetime(T(12)))

    form.confirm_button.click()

    assert (not form.isHidden(), form.title_edit.text(), form.values()[1:]) == (
        True,
        "  ",
        (T(11), T(12)),
    )


def test_ui_add_accepted_closes_form(qtbot: QtBot, make_service: MakeService) -> None:
    window = _open(qtbot, make_service)
    window.add_form.title_edit.setText("Buy milk")

    window.add_form.confirm_button.click()

    assert window.add_form.isHidden()


def test_ui_add_success_clears_stale_error_message(qtbot: QtBot, make_service: MakeService) -> None:
    window = _open(qtbot, make_service)
    window.add_form.confirm_button.click()
    window.add_form.title_edit.setText("Buy milk")

    window.add_form.confirm_button.click()

    assert window.message_label.text() == ""


def test_ui_add_form_reopen_recomputes_prefill_and_resets_title(
    qtbot: QtBot, make_service: MakeService, clock: MutableClock
) -> None:
    window = _open(qtbot, make_service)
    window.add_form.title_edit.setText("typed")
    clock.now = T(16, 10)

    window.add_button.click()

    form = window.add_form
    assert (form.title_edit.text(), form.values()[1:]) == ("", (T(17), T(17, 30)))


def test_to_datetime_drops_seconds_and_millis_and_round_trips() -> None:
    minute = to_qdatetime(datetime(2026, 1, 2, 9, 5))
    noisy = minute.addSecs(42).addMSecs(999)

    assert (to_datetime(noisy), to_qdatetime(to_datetime(noisy))) == (
        datetime(2026, 1, 2, 9, 5),
        minute,
    )
