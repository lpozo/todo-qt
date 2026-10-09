"""Contract tests for todo_qt.cli.main, its exit codes, and its helpers."""

import re
from datetime import time
from pathlib import Path

import pytest

from todo_qt import cli
from todo_qt.cli import main, new_task_id, system_clock
from todo_qt.services import PlanService


def test_main_launches_ui_with_empty_service_when_no_saved_data(tmp_path: Path) -> None:
    received: list[PlanService] = []

    def run_ui(service: PlanService) -> int:
        received.append(service)
        return 0

    code = main([], environ={"TODO_QT_DATA_DIR": str(tmp_path)}, run_ui=run_ui)

    assert code == 0
    assert len(received) == 1
    assert received[0].plan.tasks == ()
    assert received[0].plan.day_start == time(9, 0)


def test_main_rejects_unexpected_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[PlanService] = []

    def run_ui(service: PlanService) -> int:
        calls.append(service)
        return 0

    code = main(["--bogus"], run_ui=run_ui)

    assert code == 2
    assert calls == []
    assert capsys.readouterr().err != ""


def test_main_fails_when_data_dir_unusable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_file = tmp_path / "file"
    a_file.write_text("x")
    calls: list[PlanService] = []

    def run_ui(service: PlanService) -> int:
        calls.append(service)
        return 0

    code = main([], environ={"TODO_QT_DATA_DIR": str(a_file)}, run_ui=run_ui)

    assert code == 1
    assert calls == []
    assert capsys.readouterr().err != ""


def test_system_clock_returns_naive_datetime() -> None:
    assert system_clock().tzinfo is None


def test_new_task_id_is_32_lowercase_hex_chars() -> None:
    assert re.fullmatch(r"[0-9a-f]{32}", new_task_id())


def test_main_default_runner_calls_ui_run_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    received: list[PlanService] = []

    def fake_run_app(service: PlanService) -> int:
        received.append(service)
        return 5

    monkeypatch.setattr("todo_qt.ui.run_app", fake_run_app)

    code = main([], environ={"TODO_QT_DATA_DIR": str(tmp_path)})

    assert code == 5
    assert len(received) == 1
    assert cli.DATA_DIR_ENV_VAR == "TODO_QT_DATA_DIR"
