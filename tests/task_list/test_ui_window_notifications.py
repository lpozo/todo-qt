"""UI notifications: save-failure and startup-corruption messages."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from todo_qt.services import StoreCorruptError, StoreWriteError
from todo_qt.ui.main_window import MainWindow
from todo_qt.ui.messages import save_failure_message, startup_message

from .fakes import FakeStore, MakeService


def test_ui_save_failure_message_shown_and_change_kept(
    qtbot: QtBot, make_service: MakeService
) -> None:
    store = FakeStore.failing_saves(path=Path("tasks.json"), reason="disk full")
    window = MainWindow(make_service(store))
    qtbot.addWidget(window)
    window.add_button.click()
    window.add_form.title_edit.setText("Buy milk")

    window.add_form.confirm_button.click()

    expected = save_failure_message(StoreWriteError(Path("tasks.json"), "disk full"))
    assert (window.message_label.text(), window.model.rowCount()) == (expected, 1)
    assert expected == (
        "Could not save your changes (disk full). "
        "The change is kept in the list but may be lost if you close the app."
    )


def test_ui_corrupt_store_message_shown_and_list_empty(
    qtbot: QtBot, make_service: MakeService
) -> None:
    store = FakeStore.corrupt(Path("tasks.json"), "bad json")

    window = MainWindow(make_service(store))
    qtbot.addWidget(window)

    expected = startup_message(StoreCorruptError(Path("tasks.json"), "bad json"))
    assert (window.message_label.text(), window.model.rowCount()) == (expected, 0)
    assert expected == (
        "Your saved tasks could not be read (tasks.json). "
        "Starting with an empty list; the file was left untouched."
    )
