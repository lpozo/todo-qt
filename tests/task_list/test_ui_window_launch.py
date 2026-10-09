"""UI launch: the window shows the saved list and day start."""

from datetime import time

from PySide6.QtCore import Qt, QTime
from pytestqt.qtbot import QtBot

from todo_qt.ui.main_window import MainWindow
from todo_qt.ui.task_model import DONE_ROLE

from .fakes import FakeStore, MakeService, T, make_plan, make_slot, make_task


def test_ui_shows_empty_list_and_add_control_when_no_saved_tasks(
    qtbot: QtBot, make_service: MakeService
) -> None:
    window = MainWindow(make_service())
    qtbot.addWidget(window)

    assert (window.model.rowCount(), window.add_button.text()) == (0, "Add task")


def test_ui_shows_saved_tasks_in_order_with_day_start(
    qtbot: QtBot, make_service: MakeService
) -> None:
    plan = make_plan(
        make_task("a", "A", make_slot(T(8, 30), T(9, 30))),
        make_task("b", "B", make_slot(T(9, 30), T(10, 0)), done=True),
        make_task("c", "C", make_slot(T(10, 0), T(11, 0))),
        day_start=time(8, 30),
    )
    window = MainWindow(make_service(FakeStore(plan)))
    qtbot.addWidget(window)
    model = window.model

    rows = [model.index(i).data(Qt.ItemDataRole.DisplayRole) for i in range(model.rowCount())]
    assert [r.split("\n")[0] for r in rows] == ["A", "B", "C"]
    assert "2026-01-02 08:30" in rows[0]
    assert "2026-01-02 09:30" in rows[0]
    assert [model.index(i).data(DONE_ROLE) for i in range(3)] == [False, True, False]
    assert window.day_start_edit.time() == QTime(8, 30)
    assert window.day_start_edit.isReadOnly()


def test_model_refresh_picks_up_plan_changes(qtbot: QtBot, make_service: MakeService) -> None:
    service = make_service()
    window = MainWindow(service)
    qtbot.addWidget(window)
    service.add_task("New", make_slot(T(11), T(12)))

    with qtbot.waitSignal(window.model.modelReset):
        window.model.refresh()

    assert window.model.rowCount() == 1
