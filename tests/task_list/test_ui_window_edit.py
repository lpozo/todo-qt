"""UI edit mode: pre-fill, edit, reschedule, and error handling."""

from pathlib import Path

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from todo_qt.domain import TimeSlot
from todo_qt.services import StoreWriteError
from todo_qt.ui.convert import to_qdatetime
from todo_qt.ui.main_window import MainWindow
from todo_qt.ui.task_model import DONE_ROLE

from .fakes import FakeStore, MakeService, T


def _window(qtbot: QtBot, make_service: MakeService) -> MainWindow:
    service = make_service()
    service.add_task("First", _slot(9, 10))
    service.add_task("Second", _slot(11, 12))
    service.set_done(service.plan.tasks[1].id, True)
    window = MainWindow(service)
    qtbot.addWidget(window)
    return window


def _slot(start: int, end: int) -> TimeSlot:
    return TimeSlot(T(start), T(end))


def _title(window: MainWindow, row: int) -> str:
    return str(window.model.index(row).data(Qt.ItemDataRole.DisplayRole).split("\n")[0])


def test_ui_edit_form_is_prefilled_with_selected_task(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    window.open_edit_form(window.model.index(1))

    form = window.add_form
    assert (form.title_edit.text(), form.start_edit.dateTime(), form.end_edit.dateTime()) == (
        "Second",
        to_qdatetime(T(11)),
        to_qdatetime(T(12)),
    )


def test_ui_edit_button_opens_form_for_current_row(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    window.list_view.setCurrentIndex(window.model.index(0))

    window.edit_button.click()

    assert window.add_form.title_edit.text() == "First"


def test_ui_edit_title_and_slot_update_row_in_place(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(1))
    window.add_form.title_edit.setText("Renamed")
    window.add_form.start_edit.setDateTime(to_qdatetime(T(13)))
    window.add_form.end_edit.setDateTime(to_qdatetime(T(14)))

    window.add_form.confirm_button.click()

    task = window.model.index(1)
    assert (
        _title(window, 1),
        task.data(DONE_ROLE),
        window._service.plan.tasks[1].slot.start,
        window.add_form.isHidden(),
    ) == ("Renamed", True, T(13), True)


def test_ui_edit_blank_title_keeps_form_open_and_task_unchanged(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(0))
    window.add_form.title_edit.setText("  ")
    window.add_form.start_edit.setDateTime(to_qdatetime(T(15)))
    window.add_form.end_edit.setDateTime(to_qdatetime(T(16)))

    window.add_form.confirm_button.click()

    task = window._service.plan.tasks[0]
    assert (
        bool(window.message_label.text()),
        window.add_form.isHidden(),
        task.title,
        task.slot.start,
    ) == (True, False, "First", T(9))


def test_ui_edit_end_before_start_keeps_form_open_and_title_unchanged(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(0))
    window.add_form.title_edit.setText("Changed")
    window.add_form.start_edit.setDateTime(to_qdatetime(T(15)))
    window.add_form.end_edit.setDateTime(to_qdatetime(T(14)))

    window.add_form.confirm_button.click()

    assert (
        bool(window.message_label.text()),
        window.add_form.isHidden(),
        window._service.plan.tasks[0].title,
        window.add_form.title_edit.text(),
    ) == (True, False, "First", "Changed")


def test_ui_add_after_edit_adds_a_new_task(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(0))
    window.add_form.hide()

    window.add_button.click()
    window.add_form.title_edit.setText("Third")
    window.add_form.confirm_button.click()

    assert [t.title for t in window._service.plan.tasks] == ["First", "Second", "Third"]


def test_ui_edit_success_clears_stale_message(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    window.show_message("stale")
    window.open_edit_form(window.model.index(0))

    window.add_form.confirm_button.click()

    assert window.message_label.text() == ""


def test_ui_edit_leaves_other_rows_unchanged(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(1))
    window.add_form.title_edit.setText("Renamed")
    window.add_form.end_edit.setDateTime(to_qdatetime(T(13)))

    window.add_form.confirm_button.click()

    first = window._service.plan.tasks[0]
    assert (
        [_title(window, r) for r in range(2)],
        first.slot,
        [window.model.index(r).data(DONE_ROLE) for r in range(2)],
    ) == (["First", "Renamed"], _slot(9, 10), [False, True])


def test_ui_double_click_opens_edit_form_for_that_row(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.show()

    index = window.model.index(1)
    window.list_view.doubleClicked.emit(index)

    assert (window.add_form.title_edit.text(), window.add_form.isHidden()) == ("Second", False)


def test_ui_edit_button_without_selection_does_nothing(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    window.edit_button.click()

    assert window.add_form.isHidden()


def test_ui_edit_mode_resets_after_successful_edit(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(0))
    window.add_form.confirm_button.click()

    window.add_form.open_with("Third", T(15), T(16))
    window.add_form.confirm_button.click()

    assert [t.title for t in window._service.plan.tasks] == ["First", "Second", "Third"]


def test_ui_edit_save_failure_shows_message_and_keeps_change(
    qtbot: QtBot, make_service: MakeService, fake_store: FakeStore
) -> None:
    service = make_service(fake_store)
    service.add_task("First", _slot(9, 10))
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.open_edit_form(window.model.index(0))
    window.add_form.title_edit.setText("Renamed")
    fake_store.fail_next_save(StoreWriteError(Path("tasks.json"), "disk full"))

    window.add_form.confirm_button.click()

    assert (service.plan.tasks[0].title, bool(window.message_label.text())) == ("Renamed", True)


def test_ui_edit_of_vanished_task_shows_message_and_closes_form(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.open_edit_form(window.model.index(0))
    window._service.delete_task(window._service.plan.tasks[0].id)

    window.add_form.confirm_button.click()

    assert (bool(window.message_label.text()), window.add_form.isHidden()) == (True, True)
