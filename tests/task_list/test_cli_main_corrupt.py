"""Tests for main() with unreadable saved data."""

from pathlib import Path

from todo_qt.cli import main
from todo_qt.services import PlanService


def test_main_with_corrupt_data_still_launches_and_preserves_file(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "tasks.json"
    path.write_text("{broken", encoding="utf-8")
    received: list[PlanService] = []

    def run_ui(service: PlanService) -> int:
        received.append(service)
        return 0

    code = main([], environ={"TODO_QT_DATA_DIR": str(data_dir)}, run_ui=run_ui)

    assert code == 0
    assert received[0].startup_error is not None
    assert received[0].plan.tasks == ()
    assert path.read_text(encoding="utf-8") == "{broken"
