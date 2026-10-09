"""The active task contract, shared by the workflow hooks.

The orchestrator writes `.workflow/current-task.yaml` into each task worktree:
a flat, single-task copy of a `tasks.yaml` entry, plus the commit the task
branch started from (`base_ref`). Hooks import this module from their own
directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

TASK_FILE = Path(".workflow") / "current-task.yaml"


class InvalidTaskError(Exception):
    """The task contract can't be used to decide anything."""


@dataclass(frozen=True)
class Task:
    id: str
    files_in_scope: list[str]
    acceptance: str | None
    base_ref: str | None


def find_task_file(cwd: Path) -> Path | None:
    """Return the nearest task file at or above cwd, without leaving the repo."""
    for directory in (cwd, *cwd.parents):
        candidate = directory / TASK_FILE
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():  # A directory, or a file in worktrees
            return None
    return None


def load_task(task_file: Path) -> Task:
    try:
        data = yaml.safe_load(task_file.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise InvalidTaskError(f"can't read {TASK_FILE}: {error}") from error
    if not isinstance(data, dict):
        raise InvalidTaskError(f"{TASK_FILE} must be a mapping")

    files = data.get("files_in_scope")
    if not isinstance(files, list) or not files:
        raise InvalidTaskError(f"{TASK_FILE} has no files_in_scope")
    if not all(isinstance(entry, str) and entry for entry in files):
        raise InvalidTaskError(f"{TASK_FILE} files_in_scope must be non-empty strings")

    optional: dict[str, str | None] = {}
    for key in ("acceptance", "base_ref"):
        value = data.get(key)
        if value is not None and not (isinstance(value, str) and value.strip()):
            raise InvalidTaskError(f"{TASK_FILE} {key} must be a non-empty string")
        optional[key] = value

    return Task(
        id=str(data.get("id", "<no id>")),
        files_in_scope=files,
        acceptance=optional["acceptance"],
        base_ref=optional["base_ref"],
    )
