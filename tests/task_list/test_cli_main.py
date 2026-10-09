"""Tests for the composition root in todo_qt.cli."""

from pathlib import Path

from todo_qt.cli import main
from todo_qt.persistence import JsonPlanStore
from todo_qt.services import PlanService


def test_main_returns_ui_exit_code() -> None:
    assert main([], run_ui=lambda service: 7) == 7


def test_main_wires_json_store_in_default_data_dir(isolated_home: Path) -> None:
    received: list[PlanService] = []

    def run_ui(service: PlanService) -> int:
        received.append(service)
        return 0

    main([], environ={"XDG_DATA_HOME": str(isolated_home / "xdg")}, run_ui=run_ui)

    assert len(received) == 1
    assert received[0].plan.tasks == ()
    assert JsonPlanStore(isolated_home / "xdg" / "todo-qt").load() is None
