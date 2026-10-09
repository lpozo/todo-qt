#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Stop / SubagentStop hook: keep an agent working until its task is done.

Runs only when a task contract (`.workflow/current-task.yaml`) is active, and
on SubagentStop only for the agents that do task work. Checks, in order:

1. Scope: every file changed since the task's `base_ref` commit (committed,
   uncommitted, or untracked) is in `files_in_scope`. This also catches
   writes made through Bash, which the allow-list hook can't see. Without
   `base_ref`, only uncommitted changes are checked.
2. Lint: ruff, if the project configures it, on the changed Python files.
3. Types: mypy, if the project configures it, run the way the project runs
   it; only errors in changed files count.
4. Acceptance: the task's `acceptance` command exits 0.

Every check runs with the project's `.venv/bin` first on PATH, so tools
installed by `uv sync` are found without an activated venv. A configured
tool that isn't installed fails its check instead of being skipped.

To avoid an endless loop on an unfixable failure, the hook lets the agent
stop after MAX_CONSECUTIVE_BLOCKS blocks in a row, with a warning. The
orchestrator re-validates every task before merging, so nothing slips
through.

Exit codes:
    0  the agent may stop
    2  keep working; stderr is shown to the agent
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow_task import TASK_FILE, InvalidTaskError, Task, find_task_file, load_task

GATED_AGENTS = {"implementer", "test-writer"}
MAX_CONSECUTIVE_BLOCKS = 3
COUNTER_FILE = "workflow-stop-gate"  # Inside the git dir, so it's never a change
PYTHON_SUFFIXES = (".py", ".pyi")


@dataclass
class Project:
    root: Path
    env: dict[str, str]
    tool_config: dict[str, Any]
    config_error: str | None = None

    def which(self, tool: str) -> str | None:
        return shutil.which(tool, path=self.env["PATH"])

    def run(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args, cwd=self.root, env=self.env, capture_output=True, text=True, check=False
        )

    def configures(self, tool: str, *config_files: str) -> bool:
        return tool in self.tool_config or any((self.root / f).is_file() for f in config_files)


def is_gated(payload: dict[str, Any]) -> bool:
    if payload.get("hook_event_name") != "SubagentStop":
        return True
    agent_type = payload.get("agent_type")
    if not agent_type:
        return True  # Can't tell who is stopping; checking is the safe side
    # Plugin agents are namespaced, e.g. "python-workflow:implementer".
    return str(agent_type).rsplit(":", 1)[-1] in GATED_AGENTS


def load_project(root: Path) -> Project:
    env = dict(os.environ)
    venv = root / ".venv"
    if (venv / "bin").is_dir():
        env["PATH"] = os.pathsep.join([str(venv / "bin"), env.get("PATH", "")])
        env["VIRTUAL_ENV"] = str(venv)
    project = Project(root, env, tool_config={})
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            project.tool_config = tomllib.loads(pyproject.read_text()).get("tool", {})
        except tomllib.TOMLDecodeError as error:
            # Without the config, lint and type checks can't tell what applies.
            project.config_error = f"pyproject.toml is invalid: {error}"
    return project


def git_lines(project: Project, *args: str) -> list[str]:
    result = project.run(["git", *args])
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line for line in result.stdout.split("\0") if line]


def changed_files(project: Project, base_ref: str | None) -> list[str]:
    # --no-renames reports a move as a deletion plus an addition, so moving an
    # out-of-scope file away still counts as touching it.
    diff = ["diff", "--name-only", "--no-renames", "-z", base_ref or "HEAD"]
    untracked = ["ls-files", "--others", "--exclude-standard", "-z"]
    paths = set(git_lines(project, *diff)) | set(git_lines(project, *untracked))
    paths.discard(TASK_FILE.as_posix())
    return sorted(paths)


def check_scope(task: Task, changed: Iterable[str]) -> str | None:
    allowed = {os.path.normpath(entry) for entry in task.files_in_scope}
    outside = [path for path in changed if os.path.normpath(path) not in allowed]
    if not outside:
        return None
    listing = "\n".join(f"  - {path}" for path in outside)
    return (
        f"Files changed outside files_in_scope:\n{listing}\n"
        "Revert them; if the task truly needs them, stop and revisit tasks.yaml."
    )


def check_lint(project: Project, python_files: list[str]) -> str | None:
    if not python_files or not project.configures("ruff", "ruff.toml", ".ruff.toml"):
        return None
    ruff = project.which("ruff")
    if ruff is None:
        return "ruff is configured but not installed. Run `uv sync`."
    problems = []
    for args in (["check"], ["format", "--check"]):
        result = project.run([ruff, *args, "--force-exclude", *python_files])
        if result.returncode != 0:
            problems.append(f"$ ruff {' '.join(args)}\n{(result.stdout + result.stderr).strip()}")
    return "\n\n".join(problems) or None


def mypy_command(project: Project, mypy: str, python_files: list[str]) -> list[str]:
    if "files" in project.tool_config.get("mypy", {}):
        return [mypy]  # The project says what to check
    if (project.root / "src").is_dir():
        return [mypy, "src"]
    return [mypy, *python_files]


def check_types(project: Project, python_files: list[str]) -> str | None:
    if not python_files or not project.configures("mypy", "mypy.ini", ".mypy.ini"):
        return None
    mypy = project.which("mypy")
    if mypy is None:
        return "mypy is configured but not installed. Run `uv sync`."
    result = project.run(mypy_command(project, mypy, python_files))
    if result.returncode == 0:
        return None
    if result.returncode != 1:  # mypy crashed or rejected its configuration
        return (result.stdout + result.stderr).strip()
    changed = {os.path.normpath(path) for path in python_files}
    errors = [
        line
        for line in result.stdout.splitlines()
        if os.path.normpath(line.split(":", 1)[0]) in changed
    ]
    return "\n".join(errors) or None  # Errors elsewhere predate the task


def check_acceptance(project: Project, task: Task) -> str | None:
    if task.acceptance is None:
        return None
    result = project.run(["bash", "-c", task.acceptance])
    if result.returncode == 0:
        return None
    return f"$ {task.acceptance}\n{(result.stdout + result.stderr).strip()}"


def run_checks(project: Project, task: Task) -> list[tuple[str, str]]:
    if project.config_error:
        return [("pyproject", project.config_error)]
    failures: list[tuple[str, str]] = []
    if task.base_ref is None:
        print(
            "stop_gate: no base_ref in the task file; checking uncommitted changes only.",
            file=sys.stderr,
        )
    try:
        changed = changed_files(project, task.base_ref)
    except RuntimeError as error:
        return [("scope", f"{error}\nIs base_ref ({task.base_ref}) a commit in this repo?")]

    existing = [path for path in changed if (project.root / path).is_file()]
    python_files = [path for path in existing if path.endswith(PYTHON_SUFFIXES)]
    checks = (
        ("scope", check_scope(task, changed)),
        ("lint", check_lint(project, python_files)),
        ("types", check_types(project, python_files)),
        ("acceptance", check_acceptance(project, task)),
    )
    for name, failure in checks:
        if failure:
            failures.append((name, failure))
    return failures


def counter_path(project: Project) -> Path | None:
    result = project.run(["git", "rev-parse", "--absolute-git-dir"])
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()) / COUNTER_FILE


def consecutive_blocks(counter: Path | None, *, continuing: bool) -> int:
    """Return how many times in a row this hook has blocked, this one included."""
    previous = 0
    if counter is not None and continuing:
        try:
            previous = int(counter.read_text())
        except (OSError, ValueError):
            previous = 0
    return previous + 1


def main() -> int:
    payload = json.load(sys.stdin)
    if not is_gated(payload):
        return 0
    cwd = Path(payload.get("cwd") or Path.cwd())
    task_file = find_task_file(cwd)
    if task_file is None:
        return 0

    project = load_project(task_file.parent.parent.resolve())
    counter = counter_path(project)
    try:
        task = load_task(task_file)
        failures = run_checks(project, task)
    except InvalidTaskError as error:
        failures = [("task contract", str(error))]

    if not failures:
        if counter is not None:
            counter.unlink(missing_ok=True)
        return 0

    report = "\n\n".join(f"--- {name} ---\n{detail}" for name, detail in failures)
    # stop_hook_active is true when this stop attempt follows one we blocked.
    blocks = consecutive_blocks(counter, continuing=bool(payload.get("stop_hook_active")))
    if blocks >= MAX_CONSECUTIVE_BLOCKS:
        if counter is not None:
            counter.unlink(missing_ok=True)
        message = (
            f"Stop gate still failing after {blocks} attempts; letting the agent stop. "
            f"The task is NOT done.\n\n{report}"
        )
        print(json.dumps({"systemMessage": message}))
        return 0

    if counter is not None:
        counter.write_text(str(blocks))
    print(
        f"Stop gate FAILED (attempt {blocks} of {MAX_CONSECUTIVE_BLOCKS}). "
        f"Fix the following before declaring done:\n\n{report}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
