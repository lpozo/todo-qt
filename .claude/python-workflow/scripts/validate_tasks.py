# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4.18", "pyyaml>=6"]
# ///
"""Validate a tasks.yaml before any agent runs it.

JSON Schema checks the file's shape. The rules that keep parallel tasks from
colliding need the whole task graph, so they're checked here: unique ids,
existing dependencies, no cycles, exact repo-relative paths, and no file shared
by two tasks in the same layer — the tasks /orchestrate runs in parallel —
and no task owning CHANGELOG.md, which /verify writes.

Prints the layers and exits 0 if the file is valid; prints one line per
problem and exits 1 otherwise. Warnings, such as pyproject.toml in scope
without uv.lock, don't fail the check.

Usage: uv run --script validate_tasks.py docs/workflow/<slug>/tasks.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator

# Installed side by side: python-workflow/scripts/ and python-workflow/templates/.
SCHEMA = Path(__file__).resolve().parent.parent / "templates" / "tasks.schema.json"
TASK_FILE = ".workflow/current-task.yaml"
CHANGELOG = "CHANGELOG.md"  # Written by /verify, once for the whole change
# Files that change together: a new dependency edits both.
LOCKED_PAIR = ("pyproject.toml", "uv.lock")
GLOB_CHARS = set("*?[")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a workflow tasks.yaml.")
    parser.add_argument("tasks_file", type=Path)
    args = parser.parse_args(argv)

    try:
        data = yaml.safe_load(args.tasks_file.read_text())
    except (OSError, yaml.YAMLError) as error:
        print(f"{args.tasks_file}: can't read it: {error}", file=sys.stderr)
        return 1

    problems = schema_problems(data)
    layers: list[list[str]] = []
    warnings: list[str] = []
    if not problems:
        problems, layers = graph_problems(data["tasks"])
        problems += feature_problems(data["feature"], args.tasks_file)
        warnings = [warning for task in data["tasks"] for warning in task_warnings(task)]

    for warning in warnings:
        print(f"  warning: {warning}", file=sys.stderr)
    if problems:
        print(f"{args.tasks_file}: {len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    count = sum(len(layer) for layer in layers)
    print(f"{args.tasks_file}: OK — {count} task(s) in {len(layers)} layer(s)")
    for number, layer in enumerate(layers):
        parallel = f" ({len(layer)} in parallel)" if len(layer) > 1 else ""
        print(f"  Layer {number}{parallel}: {', '.join(layer)}")
    return 0


def schema_problems(data: Any) -> list[str]:
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))
    return [
        f"{_location(error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda e: list(map(str, e.path)))
    ]


def graph_problems(tasks: list[dict[str, Any]]) -> tuple[list[str], list[list[str]]]:
    problems: list[str] = []
    ids = [task["id"] for task in tasks]
    for task_id, count in Counter(ids).items():
        if count > 1:
            problems.append(f"{task_id}: id used by {count} tasks")

    known = set(ids)
    for task in tasks:
        for dependency in task["depends_on"]:
            if dependency == task["id"]:
                problems.append(f"{task['id']}: depends on itself")
            elif dependency not in known:
                problems.append(f"{task['id']}: depends on unknown task {dependency}")
        problems += [f"{task['id']}: {problem}" for problem in path_problems(task)]
        if not task["acceptance"].strip():
            problems.append(f"{task['id']}: acceptance command is blank")
    if problems:
        return problems, []

    graph = {task["id"]: task["depends_on"] for task in tasks}
    cycle = find_cycle(graph)
    if cycle:
        return [f"dependency cycle (→ means depends on): {' → '.join(cycle)}"], []

    layers = layer_tasks(graph)
    files = {task["id"]: task["files_in_scope"] for task in tasks}
    for number, layer in enumerate(layers):
        owners: dict[str, list[str]] = defaultdict(list)
        for task_id in layer:
            for path in files[task_id]:
                owners[path].append(task_id)
        for path, task_ids in owners.items():
            if len(task_ids) > 1:
                problems.append(
                    f"{path}: in scope for {', '.join(task_ids)}, which run in parallel "
                    f"(layer {number}); sequence them with depends_on, or split the file"
                )
    return problems, layers


def path_problems(task: dict[str, Any]) -> list[str]:
    """The allow-list hook matches exact repo-relative paths; anything else never matches."""
    problems = []
    for path in task["files_in_scope"]:
        normalized = PurePosixPath(path).as_posix()
        if path.startswith("/"):
            problems.append(f"{path}: must be relative to the repo root")
        elif "\\" in path:
            problems.append(f"{path}: use forward slashes")
        elif ".." in PurePosixPath(path).parts:
            problems.append(f"{path}: must stay inside the repo (no '..')")
        elif normalized != path:
            problems.append(f"{path}: write it normalized, as {normalized}")
        elif GLOB_CHARS & set(path):
            problems.append(f"{path}: globs aren't supported; list each file")
        elif path == TASK_FILE:
            problems.append(f"{path}: the task contract is read-only for tasks")
        elif path == CHANGELOG:
            problems.append(f"{path}: /verify writes the changelog entry, not a task")
    return problems


def task_warnings(task: dict[str, Any]) -> list[str]:
    """Allowed, but usually a mistake."""
    in_scope = set(task["files_in_scope"])
    first, second = LOCKED_PAIR
    for present, missing in ((first, second), (second, first)):
        if present in in_scope and missing not in in_scope:
            return [
                f"{task['id']}: {present} is in scope without {missing}; "
                "adding a dependency changes both"
            ]
    return []


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle as a path along depends_on edges, starting and ending on one task."""
    visiting: list[str] = []
    done: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            return [*visiting[visiting.index(node) :], node]
        if node in done:
            return None
        visiting.append(node)
        for dependency in graph[node]:
            cycle = visit(dependency)
            if cycle:
                return cycle
        visiting.pop()
        done.add(node)
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def layer_tasks(graph: dict[str, list[str]]) -> list[list[str]]:
    """Group tasks by depth: a task runs one layer after its deepest dependency."""
    depth: dict[str, int] = {}

    def depth_of(node: str) -> int:
        if node not in depth:
            depth[node] = 1 + max((depth_of(d) for d in graph[node]), default=-1)
        return depth[node]

    layers: list[list[str]] = []
    for node in graph:
        level = depth_of(node)
        while len(layers) <= level:
            layers.append([])
    for node in graph:  # Keep file order within a layer
        layers[depth[node]].append(node)
    return layers


def feature_problems(feature: str, tasks_file: Path) -> list[str]:
    """In docs/workflow/<slug>/tasks.yaml, the feature must be the folder's slug."""
    folder = tasks_file.resolve().parent
    if folder.parent.name == "workflow" and feature != folder.name:
        return [f"feature: is {feature!r}, but the file is in docs/workflow/{folder.name}/"]
    return []


def _location(path: Any) -> str:
    parts = list(path)
    if not parts:
        return "tasks.yaml"
    text = str(parts[0])
    for part in parts[1:]:
        text += f"[{part}]" if isinstance(part, int) else f".{part}"
    return text


if __name__ == "__main__":
    sys.exit(main())
