"""Command-line entry point and composition root for todo-qt."""

import os
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from todo_qt.domain import TaskId
from todo_qt.persistence import JsonPlanStore, default_data_dir
from todo_qt.services import PlanService

DATA_DIR_ENV_VAR = "TODO_QT_DATA_DIR"

type UiRunner = Callable[[PlanService], int]


def resolve_data_dir(environ: Mapping[str, str], default_dir: Path) -> Path:
    """Return the data directory to use (environment override comes later)."""
    return default_dir


def system_clock() -> datetime:
    """Return the current naive local time."""
    return datetime.now()


def new_task_id() -> TaskId:
    """Return a fresh unique task id."""
    return TaskId(uuid.uuid4().hex)


def _run_qt_ui(service: PlanService) -> int:
    from todo_qt.ui import run_app

    return run_app(service)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    run_ui: UiRunner | None = None,
) -> int:
    """Wire the application together, run the UI, and return its exit code."""
    env = os.environ if environ is None else environ
    runner = _run_qt_ui if run_ui is None else run_ui
    default_dir = default_data_dir(env, Path.home(), sys.platform)
    directory = resolve_data_dir(env, default_dir)
    service = PlanService(JsonPlanStore(directory), system_clock, new_task_id)
    return runner(service)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
