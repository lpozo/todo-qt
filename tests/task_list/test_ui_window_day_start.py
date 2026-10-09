"""UI day-start control."""

from datetime import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTime
from pytestqt.qtbot import QtBot

from todo_qt.domain import TimeSlot
from todo_qt.services import StoreWriteError
from todo_qt.ui.controller import UiController
from todo_qt.ui.main_window import MainWindow
from todo_qt.ui.messages import save_failure_message

from .fakes import FRI, FakeStore, MakeService, RecordingStore, T, make_plan, make_task

ERROR = StoreWriteError(Path("tasks.json"), "disk full")


def _plan_store() -> FakeStore:
    return FakeStore(
        make_plan(
            make_task("a", "A", TimeSlot(T(10), T(11))),
            make_task("b", "B", TimeSlot(T(11), T(12))),
            day_start=time(9, 0),
        )
    )


def _window(qtbot: QtBot, make_service: MakeService, store: object = None) -> MainWindow:
    service = make_service(store if store is not None else _plan_store())  # type: ignore[arg-type]
    window = MainWindow(service)
    qtbot.addWidget(window)
    return window


def _rows(window: MainWindow) -> list[str]:
    rows = range(window.model.rowCount())
    texts = (str(window.model.index(r).data(Qt.ItemDataRole.DisplayRole)) for r in rows)
    return [text.replace("\n", " ").replace(f"{FRI} ", "") for text in texts]


def _type_time(window: MainWindow, hour: int, minute: int) -> None:
    window.day_start_edit.setTime(QTime(hour, minute))
    window.day_start_edit.editingFinished.emit()


def test_ui_change_day_start_rechains_displayed_times(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    _type_time(window, 8, 0)

    assert (_rows(window), window.day_start_edit.time()) == (
        ["A 08:00 - 09:00", "B 09:00 - 10:00"],
        QTime(8, 0),
    )


def test_ui_day_start_control_is_editable(qtbot: QtBot, make_service: MakeService) -> None:
    window = _window(qtbot, make_service)

    assert not window.day_start_edit.isReadOnly()


def test_ui_day_start_shows_default_for_empty_store(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service, FakeStore())

    assert window.day_start_edit.time() == QTime(9, 0)


def test_ui_refresh_updates_day_start_after_service_change(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    window._service.set_day_start(time(7, 30))
    window.refresh()

    assert window.day_start_edit.time() == QTime(7, 30)


def test_ui_refresh_does_not_trigger_day_start_change(
    qtbot: QtBot, make_service: MakeService
) -> None:
    store = RecordingStore(_plan_store())
    window = _window(qtbot, make_service, store)
    window._service.set_day_start(time(7, 30))
    saves = len(store.saves)
    fired: list[str] = []
    window.day_start_edit.editingFinished.connect(lambda: fired.append("finished"))
    window.day_start_edit.timeChanged.connect(lambda _t: fired.append("changed"))

    window.refresh()

    assert (fired, len(store.saves)) == ([], saves)


def test_ui_editing_finished_with_unchanged_value_does_not_save(
    qtbot: QtBot, make_service: MakeService
) -> None:
    store = RecordingStore(_plan_store())
    window = _window(qtbot, make_service, store)

    window.day_start_edit.editingFinished.emit()

    assert store.saves == []


def test_ui_day_start_does_not_rechain_on_every_keystroke(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)

    window.day_start_edit.setTime(QTime(8, 0))

    assert (_rows(window), window._service.plan.day_start) == (
        ["A 10:00 - 11:00", "B 11:00 - 12:00"],
        time(9, 0),
    )


def test_ui_day_start_save_failure_shows_message_and_keeps_change(
    qtbot: QtBot, make_service: MakeService
) -> None:
    store = _plan_store()
    window = _window(qtbot, make_service, store)
    store.save_error = ERROR

    _type_time(window, 8, 0)

    assert (window.message_label.text(), _rows(window)) == (
        save_failure_message(ERROR),
        ["A 08:00 - 09:00", "B 09:00 - 10:00"],
    )


def test_ui_day_start_change_leaves_add_form_prefill_unchanged(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    before = window._service.default_slot()

    _type_time(window, 8, 0)

    assert window._service.default_slot() == before


def test_ui_controller_set_day_start_notifies_change(make_service: MakeService) -> None:
    service = make_service(_plan_store())
    changes: list[int] = []
    controller = UiController(service, lambda _m: None, lambda: changes.append(1))

    accepted = controller.set_day_start(time(8, 0))

    assert (accepted, service.plan.day_start, len(changes)) == (True, time(8, 0), 1)


def test_ui_controller_set_day_start_notifies_save_failure(make_service: MakeService) -> None:
    service = make_service(FakeStore(make_plan(), save_error=ERROR))
    messages: list[str] = []
    controller = UiController(service, messages.append, lambda: None)

    controller.set_day_start(time(8, 0))

    assert messages == [save_failure_message(ERROR)]


def test_ui_repeated_editing_finished_keeps_save_failure_message(
    qtbot: QtBot, make_service: MakeService
) -> None:
    store = _plan_store()
    window = _window(qtbot, make_service, store)
    store.save_error = ERROR
    _type_time(window, 8, 0)

    window.day_start_edit.editingFinished.emit()

    assert window.message_label.text() == save_failure_message(ERROR)


def test_ui_editing_finished_without_edit_keeps_existing_message(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.show_message("startup problem")

    window.day_start_edit.editingFinished.emit()

    assert window.message_label.text() == "startup problem"


def test_ui_pressing_enter_in_day_start_control_applies_it(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = _window(qtbot, make_service)
    window.show()
    window.day_start_edit.setFocus()
    window.day_start_edit.setTime(QTime(8, 0))

    qtbot.keyClick(window.day_start_edit, Qt.Key.Key_Return)

    assert _rows(window) == ["A 08:00 - 09:00", "B 09:00 - 10:00"]


def test_ui_rejected_day_start_snaps_control_back(
    qtbot: QtBot, make_service: MakeService, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(qtbot, make_service)
    monkeypatch.setattr(window.controller, "set_day_start", lambda _t: False)

    _type_time(window, 8, 0)

    assert window.day_start_edit.time() == QTime(9, 0)
