#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""PostToolUse hook: format an edited Python file with the project's ruff.

Registered for Edit and Write. Runs only in projects that configure ruff
(`[tool.ruff]` in pyproject.toml, or ruff.toml / .ruff.toml), so projects
formatted by something else are left alone. Prefers the project's
.venv/bin/ruff, so no activated venv is needed.

Never blocks: always exits 0. If ruff is configured but missing, or the file
can't be formatted, the stop gate reports it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PYTHON_SUFFIXES = (".py", ".pyi")
RUFF_CONFIG_FILES = ("ruff.toml", ".ruff.toml")


def find_project_root(path: Path) -> Path | None:
    """Return the nearest directory above path with project config, within the repo."""
    for directory in path.parents:
        if (directory / "pyproject.toml").is_file() or any(
            (directory / name).is_file() for name in RUFF_CONFIG_FILES
        ):
            return directory
        if (directory / ".git").exists():
            return None
    return None


def uses_ruff(root: Path) -> bool:
    if any((root / name).is_file() for name in RUFF_CONFIG_FILES):
        return True
    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return "ruff" in pyproject.get("tool", {})


def find_ruff(root: Path) -> str | None:
    venv_ruff = root / ".venv" / "bin" / "ruff"
    if venv_ruff.is_file():
        return str(venv_ruff)
    return shutil.which("ruff")


def main() -> int:
    payload = json.load(sys.stdin)
    raw_path = (payload.get("tool_input") or {}).get("file_path")
    if not raw_path:
        return 0
    path = (Path(payload.get("cwd") or Path.cwd()) / raw_path).resolve()
    if path.suffix not in PYTHON_SUFFIXES or not path.is_file():
        return 0

    root = find_project_root(path)
    if root is None or not uses_ruff(root):
        return 0
    ruff = find_ruff(root)
    if ruff is None:
        return 0

    result = subprocess.run(
        [ruff, "format", "--force-exclude", str(path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"ruff format failed on {path} (non-blocking):\n{result.stderr}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
