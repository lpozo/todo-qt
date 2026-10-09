#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""PreToolUse hook: block file edits outside the active task's allow-list.

Registered for Edit, Write, and NotebookEdit. Reads the hook input JSON from
stdin and finds the governing `.workflow/current-task.yaml`: first in the
edited file's directory or a parent (so an edit lands under the contract of
the worktree it's in, wherever the agent's shell is), then in the hook's cwd
or a parent. Each search stops at its git root. Without a task file, every
edit is allowed.

Paths are compared after full resolution (`.`, `..`, symlinks), so any
spelling of an allowed file matches, and nothing outside the task's root
does. The task contract is read-only to the agents it governs: subagents,
and any session working inside the task's directory. The orchestrator, in
the main session outside the worktree, may write it.

Exit codes:
    0  allow
    1  hook error; Claude Code reports it but doesn't block
    2  block; stderr is shown to Claude

Writes made through the Bash tool never reach this hook. The stop gate
catches those afterward by diffing the task branch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from workflow_task import TASK_FILE, InvalidTaskError, find_task_file, load_task

PATH_KEYS = ("file_path", "notebook_path")


def target_path(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input") or {}
    for key in PATH_KEYS:
        if value := tool_input.get(key):
            return str(value)
    return None


def governed_by(root: Path, payload: dict[str, Any], cwd: Path) -> bool:
    """Whether the caller is an agent working under this task's contract."""
    # Claude Code adds agent_type to the input of hooks fired by subagents.
    return bool(payload.get("agent_type")) or cwd.resolve().is_relative_to(root)


def block(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"enforce_allowlist: can't parse hook input: {error}", file=sys.stderr)
        return 1

    raw_target = target_path(payload)
    if raw_target is None:
        return 0
    cwd = Path(payload.get("cwd") or Path.cwd())
    target = (cwd / raw_target).resolve()  # An absolute raw_target replaces cwd

    task_file = find_task_file(target.parent) or find_task_file(cwd)
    if task_file is None:
        return 0
    root = task_file.parent.parent.resolve()

    if target == task_file.resolve():
        if not governed_by(root, payload, cwd):
            return 0  # The orchestrator writing the contract
        return block(
            f"BLOCKED: {TASK_FILE} is the task contract and is read-only.\n"
            "To change the task's scope, stop and revisit task boundaries in tasks.yaml."
        )

    try:
        task = load_task(task_file)
    except InvalidTaskError as error:
        return block(f"BLOCKED: {error}; can't enforce the allow-list.")

    if target in {(root / entry).resolve() for entry in task.files_in_scope}:
        return 0

    allowed = "\n".join(f"  - {entry}" for entry in task.files_in_scope)
    return block(
        f"BLOCKED: '{raw_target}' is outside the active task's files_in_scope.\n\n"
        f"Active task: {task.id}\n"
        f"Allowed files:\n{allowed}\n\n"
        "If this file genuinely needs to be edited, halt and revisit task boundaries\n"
        "in tasks.yaml — do NOT bypass the hook."
    )


if __name__ == "__main__":
    raise SystemExit(main())
