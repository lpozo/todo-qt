# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Check a project against the workflow baseline, without changing it.

Runs the mechanical checks behind /env-doctor — files, config sections, git
setup, the workflow install — and, unless --no-smoke, the tools themselves in
check-only mode. Each failure has a severity and a fix; /env-doctor explains
them. Exits 0 if nothing failed, 1 otherwise.

Usage: uv run --script doctor.py [project-dir] [--no-smoke]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Installed side by side: python-workflow/scripts/ and python-workflow/templates/.
RULES_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "workflow-rules.md"
RULES_FILE = Path(".claude/rules/python-workflow.md")
MANIFEST = Path(".claude/python-workflow/manifest.json")
ADR_0001 = Path("docs/adr/0001-architecture-style.md")
STYLES = ("simple modules", "layered", "hexagonal")
COVERAGE_TARGET = 85
LOCAL_HOOKS = ("ruff-check", "ruff-format", "bandit", "mypy", "pytest")
GIT_HOOKS = ("pre-commit", "commit-msg", "pre-push")
# Path -> severity if git doesn't ignore it. The orchestrator relies on the first two.
IGNORED = {
    ".workflow/current-task.yaml": "critical",
    ".worktrees/": "critical",
    ".venv/": "important",
    "__pycache__/": "important",
    "mutants/": "nice",
}
SEVERITIES = ("critical", "important", "nice")


@dataclass
class Result:
    section: str
    name: str
    status: str  # "pass", "fail", or "info"
    detail: str = ""
    fix: str = ""
    severity: str = ""  # Failures only


class Doctor:
    def __init__(self, root: Path, *, smoke: bool) -> None:
        self.root = root
        self.smoke = smoke
        self.results: list[Result] = []
        self.section = ""
        self.pyproject: dict[str, Any] | None = None
        self.style: str | None = None
        self.in_git = False
        # The project's own tools, not this script's environment; no bytecode files.
        self.env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(self) -> list[Result]:
        sections = (
            ("Runtime", self.runtime),
            ("Project metadata", self.metadata),
            ("Layout", self.layout),
            ("Tool configs", self.tool_configs),
            ("Pre-commit", self.pre_commit),
            ("CI", self.ci),
            ("Workflow bundle", self.workflow_bundle),
            ("Adoption baselines", self.baselines),
            ("Smoke", self.smoke_tests),
        )
        for title, section in sections:
            self.section = title
            section()
        return self.results

    # -- Recording ---------------------------------------------------------------------

    def check(
        self, name: str, ok: bool, *, fix: str, severity: str = "important", detail: str = ""
    ) -> bool:
        status = "pass" if ok else "fail"
        self.results.append(
            Result(self.section, name, status, detail, "" if ok else fix, "" if ok else severity)
        )
        return ok

    def info(self, name: str, detail: str) -> None:
        self.results.append(Result(self.section, name, "info", detail))

    # -- Sections ----------------------------------------------------------------------

    def runtime(self) -> None:
        self.check(
            "uv available",
            shutil.which("uv") is not None,
            fix="curl -LsSf https://astral.sh/uv/install.sh | sh",
            severity="critical",
        )
        self.check(
            "git available", shutil.which("git") is not None, fix="Install git", severity="critical"
        )
        self.in_git = self.check(
            "inside a git repository",
            self.git("rev-parse", "--git-dir").returncode == 0,
            fix="git init (or run /env-bootstrap)",
            severity="critical",
        )

    def metadata(self) -> None:
        path = self.root / "pyproject.toml"
        if not self.check(
            "pyproject.toml exists", path.is_file(), fix="Run /env-bootstrap", severity="critical"
        ):
            return
        try:
            self.pyproject = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError as error:
            self.check(
                "pyproject.toml parses",
                False,
                detail=str(error),
                fix="Fix the TOML syntax",
                severity="critical",
            )
            return
        project = self.pyproject.get("project", {})
        self.check(
            "[project] table (PEP 621)",
            bool(project),
            fix="Run /env-bootstrap",
            severity="critical",
        )
        spec = project.get("requires-python")
        if self.check(
            "requires-python set", bool(spec), fix='Add requires-python = ">=3.12" to [project]'
        ):
            found = self.command("uv", "python", "find", spec)
            self.check(
                f"a Python matching {spec} is available",
                found.returncode == 0,
                fix=f'uv python install "{spec}"',
            )
        self.check(
            "[dependency-groups] dev",
            "dev" in self.pyproject.get("dependency-groups", {}),
            fix="Add the dev group from /env-bootstrap",
        )
        lock = self.root / "uv.lock"
        if self.check("uv.lock exists", lock.is_file(), fix="uv lock", severity="critical"):
            result = self.command("uv", "lock", "--check")
            self.check(
                "uv.lock matches pyproject.toml",
                result.returncode == 0,
                detail=_tail(result.stderr, 1),
                fix="uv lock, then commit uv.lock",
            )

    def layout(self) -> None:
        for folder, severity in (
            ("src", "critical"),
            ("tests", "critical"),
            ("docs/workflow", "important"),
        ):
            self.check(
                f"{folder}/ exists",
                (self.root / folder).is_dir(),
                fix=f"mkdir -p {folder} (or run /env-bootstrap)",
                severity=severity,
            )
        adr = self.root / ADR_0001
        title = adr.read_text().splitlines()[0].lower() if adr.is_file() else ""
        named = [style for style in STYLES if style in title]
        if self.check(
            f"{ADR_0001} names one architecture style",
            len(named) == 1,
            detail=f"title: {title!r}" if title else "missing",
            fix="Run /env-bootstrap's ADR-0001 step",
        ):
            self.style = named[0]
            self.info("architecture style", self.style)
        for path, severity in IGNORED.items() if self.in_git else ():
            self.check(
                f"git ignores {path}",
                self.git("check-ignore", "-q", path).returncode == 0,
                fix=f"Add {path} to .gitignore (see /env-bootstrap)",
                severity=severity,
            )

    def tool_configs(self) -> None:
        if self.pyproject is None:
            return
        tool = self.pyproject.get("tool", {})
        self.check("[tool.ruff]", "ruff" in tool, fix="Copy [tool.ruff] from /env-bootstrap")
        self.check(
            "[tool.mypy] strict = true",
            tool.get("mypy", {}).get("strict") is True,
            fix="Add strict = true to [tool.mypy]",
        )
        self.check(
            "[tool.pytest.ini_options]",
            "ini_options" in tool.get("pytest", {}),
            fix="Copy [tool.pytest.ini_options] from /env-bootstrap",
        )
        coverage = tool.get("coverage", {})
        self.check(
            "[tool.coverage.run] branch = true",
            coverage.get("run", {}).get("branch") is True,
            fix="Add branch = true to [tool.coverage.run]",
        )
        self.check(
            "[tool.coverage.report] fail_under set",
            "fail_under" in coverage.get("report", {}),
            fix=f"Add fail_under = {COVERAGE_TARGET} to [tool.coverage.report]",
        )
        importlinter = tool.get("importlinter")
        if self.style in ("layered", "hexagonal"):
            self.check(
                "[tool.importlinter] with include_external_packages = true",
                bool(importlinter) and importlinter.get("include_external_packages") is True,
                fix=f"ADR-0001 says {self.style}: copy [tool.importlinter] from /env-bootstrap",
            )
        elif self.style == "simple modules" and importlinter is not None:
            self.info("[tool.importlinter]", "present, though ADR-0001 says simple modules")

    def pre_commit(self) -> None:
        path = self.root / ".pre-commit-config.yaml"
        if not self.check(
            ".pre-commit-config.yaml exists", path.is_file(), fix="Copy it from /env-bootstrap"
        ):
            return
        try:
            config = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as error:
            self.check(
                ".pre-commit-config.yaml parses", False, detail=str(error), fix="Fix the YAML"
            )
            return
        hooks = {
            hook.get("id"): (repo.get("repo"), hook)
            for repo in config.get("repos", [])
            for hook in repo.get("hooks", [])
        }
        not_via_uv = [
            hook_id
            for hook_id in LOCAL_HOOKS
            if hook_id not in hooks
            or hooks[hook_id][0] != "local"
            or not str(hooks[hook_id][1].get("entry", "")).startswith("uv run --frozen ")
        ]
        self.check(
            "local hooks run via uv run --frozen",
            not not_via_uv,
            detail="missing or different: " + ", ".join(not_via_uv) if not_via_uv else "",
            fix="Copy the local hooks from /env-bootstrap",
        )
        self.check("gitleaks hook", "gitleaks" in hooks, fix="Copy it from /env-bootstrap")
        conventional = hooks.get("conventional-pre-commit", (None, {}))[1]
        self.check(
            "conventional-pre-commit hook at commit-msg",
            "commit-msg" in conventional.get("stages", []),
            fix="Copy it from /env-bootstrap",
        )
        if not self.in_git:
            return
        hooks_dir = self.git("rev-parse", "--git-path", "hooks").stdout.strip()
        missing = [name for name in GIT_HOOKS if not (self.root / hooks_dir / name).is_file()]
        self.check(
            "git hooks installed",
            bool(hooks_dir) and not missing,
            detail="missing: " + ", ".join(missing) if missing else "",
            fix="uv run pre-commit install",
        )

    def ci(self) -> None:
        path = self.root / ".github/workflows/ci.yml"
        if not self.check(
            ".github/workflows/ci.yml exists", path.is_file(), fix="Run /env-ci-setup"
        ):
            return
        text = path.read_text()
        missing = [tool for tool in ("ruff", "mypy", "pytest") if tool not in text]
        self.check(
            "CI runs ruff, mypy, and pytest",
            not missing,
            detail="not found: " + ", ".join(missing) if missing else "",
            fix="Run /env-ci-setup",
        )

    def workflow_bundle(self) -> None:
        manifest_path = next(
            (base / MANIFEST for base in (self.root, Path.home()) if (base / MANIFEST).is_file()),
            None,
        )
        if not self.check(
            "python-workflow installed",
            manifest_path is not None,
            fix="python-workflow install <project-dir>, or python-workflow install for all",
            severity="critical",
        ):
            return
        assert manifest_path is not None
        manifest = json.loads(manifest_path.read_text())
        self.info(
            "installation", f"{manifest.get('scope')} {manifest.get('version')}, {manifest_path}"
        )
        settings_path = manifest_path.parents[1] / manifest.get("settings_file", "settings.json")
        settings = json.loads(settings_path.read_text()) if settings_path.is_file() else {}
        commands = [
            str(entry.get("command", ""))
            for groups in settings.get("hooks", {}).values()
            for group in groups
            for entry in group.get("hooks", [])
        ]
        self.check(
            f"hooks registered in {settings_path.name}",
            any("python-workflow/hooks/" in command for command in commands),
            fix="Rerun python-workflow install; add -v to list the hook entries",
            severity="critical",
        )
        rules = self.root / RULES_FILE
        if (
            self.check(
                f"{RULES_FILE} exists",
                rules.is_file(),
                fix="Run /env-bootstrap's workflow-rules step",
                severity="critical",
            )
            and RULES_TEMPLATE.is_file()
        ):
            self.check(
                f"{RULES_FILE} matches the installed version",
                rules.read_bytes() == RULES_TEMPLATE.read_bytes(),
                fix=(
                    "Project install: rerun python-workflow install <project-dir>. Global install: "
                    f"copy {RULES_TEMPLATE} over it and review the diff before committing"
                ),
            )

    def baselines(self) -> None:
        """Debt recorded when an existing project adopted the workflow; it should only shrink."""
        if self.pyproject is None:
            return
        tool = self.pyproject.get("tool", {})
        exempt = [
            module
            for override in tool.get("mypy", {}).get("overrides", [])
            if override.get("ignore_errors") is True
            for module in _as_list(override.get("module"))
        ]
        if exempt:
            self.info("modules exempt from strict mypy", str(len(exempt)))
        noqa = self.git("grep", "-c", "# noqa", "--", "*.py").stdout.splitlines()
        count = sum(int(line.rsplit(":", 1)[1]) for line in noqa if ":" in line)
        if count:
            self.info("suppressed lint findings (# noqa)", str(count))
        floor = tool.get("coverage", {}).get("report", {}).get("fail_under")
        if isinstance(floor, int | float) and floor < COVERAGE_TARGET:
            self.info("coverage floor", f"fail_under = {floor} (target {COVERAGE_TARGET})")
            ci = self.root / ".github/workflows/ci.yml"
            self.check(
                "changed-lines coverage job in CI",
                ci.is_file() and "changed-lines-coverage" in ci.read_text(),
                fix="Add the changed-lines-coverage job from /env-ci-setup",
            )

    def smoke_tests(self) -> None:
        if not self.smoke or self.pyproject is None:
            return
        if not (self.root / ".venv").is_dir():
            self.check("project environment exists", False, fix="uv sync")
            return
        # Check-only, with every cache off, so the run leaves no files behind.
        commands = [
            ("ruff check .", ["ruff", "check", "--no-cache", "--output-format", "concise", "."]),
            ("ruff format --check .", ["ruff", "format", "--check", "--no-cache", "."]),
            ("mypy src", ["mypy", "--cache-dir", os.devnull, "src"]),
            ("pytest --collect-only", ["pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]),
        ]
        if "importlinter" in self.pyproject.get("tool", {}):
            commands.append(("lint-imports", ["lint-imports", "--no-cache"]))
        for name, command in commands:
            # --no-sync: never touch the environment; report what's there.
            result = self.command("uv", "run", "--no-sync", *command)
            output = result.stdout + result.stderr
            if command[:2] == ["ruff", "format"]:  # Name the files, not a diff fragment
                output = "\n".join(
                    line.strip()
                    for line in output.splitlines()
                    if "-->" in line or "eformat" in line
                )
            self.check(
                name,
                result.returncode == 0,
                detail=_tail(output, 5),
                fix=f"uv run {name}, and fix what it reports",
            )

    # -- Helpers -----------------------------------------------------------------------

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.command("git", *args)

    def command(self, *args: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                args,
                cwd=self.root,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return subprocess.CompletedProcess(args, 127, "", str(error))


def render(root: Path, results: list[Result]) -> str:
    lines = [f"Workflow baseline: {root}"]
    section = None
    for result in results:
        if result.section != section:
            section = result.section
            lines += ["", section]
        mark = {"pass": "✓", "fail": "✗", "info": "·"}[result.status]
        tag = f"[{result.severity}] " if result.severity else ""
        detail = f": {result.detail}" if result.detail and result.status == "info" else ""
        lines.append(f"  {mark} {tag}{result.name}{detail}")
        if result.status == "fail":
            for text in result.detail.splitlines():
                lines.append(f"      {text}")
            lines.append(f"      fix: {result.fix}")
    failures = [r for r in results if r.status == "fail"]
    by_severity = ", ".join(
        f"{n} {s}" for s in SEVERITIES if (n := sum(r.severity == s for r in failures))
    )
    passed = sum(r.status == "pass" for r in results)
    lines += [
        "",
        f"{passed} passed, {len(failures)} failed" + (f" ({by_severity})" if failures else ""),
    ]
    return "\n".join(lines)


def _tail(text: str, count: int) -> str:
    return "\n".join(text.strip().splitlines()[-count:])


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value or []]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a project against the workflow baseline.")
    parser.add_argument("project_dir", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--no-smoke", action="store_true", help="skip running ruff, mypy, pytest, and lint-imports"
    )
    args = parser.parse_args(argv)
    root = args.project_dir.resolve()
    results = Doctor(root, smoke=not args.no_smoke).run()
    print(render(root, results))
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
