"""Walking-skeleton smoke tests that build the real window."""

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from todo_qt.persistence import JsonPlanStore
from todo_qt.services import PlanService
from todo_qt.ui import run_app
from todo_qt.ui.main_window import MainWindow

from .fakes import IdCounter, MakeService, MutableClock


def test_walking_skeleton_window_shows_empty_list_from_json_store(
    qtbot: QtBot, tmp_path: Path, clock: MutableClock, new_id: IdCounter
) -> None:
    service = PlanService(JsonPlanStore(tmp_path), clock, new_id)
    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window.model.rowCount() == 0


def test_run_app_returns_zero_after_quit(qtbot: QtBot, make_service: MakeService) -> None:
    QTimer.singleShot(0, QApplication.quit)

    assert run_app(make_service()) == 0
