"""Tests for main() with saved data and the data-dir override."""

from pathlib import Path

from todo_qt.cli import main
from todo_qt.persistence import JsonPlanStore
from todo_qt.services import PlanService

from .fakes import T, make_plan, make_slot, make_task


def test_main_reads_and_saves_in_override_dir(tmp_path: Path, isolated_home: Path) -> None:
    override = tmp_path / "override"

    def run_ui(service: PlanService) -> int:
        service.add_task("Write", make_slot(T(9), T(10)))
        return 0

    main([], environ={"TODO_QT_DATA_DIR": str(override)}, run_ui=run_ui)

    saved = JsonPlanStore(override).load()
    assert saved is not None
    assert [t.title for t in saved.tasks] == ["Write"]
    assert not (isolated_home / "xdg-data" / "todo-qt").exists()


def test_main_launches_ui_with_saved_tasks(data_dir: Path) -> None:
    plan = make_plan(make_task("a", "One"), make_task("b", "Two", make_slot(T(11), T(12))))
    JsonPlanStore(data_dir).save(plan)
    received: list[PlanService] = []

    def run_ui(service: PlanService) -> int:
        received.append(service)
        return 0

    main([], environ={"TODO_QT_DATA_DIR": str(data_dir)}, run_ui=run_ui)

    assert received[0].plan == plan
