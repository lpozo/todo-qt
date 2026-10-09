---
name: env-bootstrap
description: Bootstrap a new Python project, or adopt an existing one, with the workflow's recommended toolchain — pyproject.toml (PEP 621), uv lockfile, dev deps (ruff/mypy/pytest/hypothesis/pre-commit), tool configs, src+tests layout, .gitignore, pre-commit hooks — tailored to the project type, with the architecture style recorded as ADR-0001. Use once per new project, before /req-research. Idempotent — safe to re-run on partial setups.
---

# env-bootstrap — One-shot Python project init

Your job: take a directory — empty, partially set up, or an existing project with its own history and tools — and bring it to the workflow's baseline. Idempotent — never destroy existing config; merge or skip. For an existing code base, follow *Adopting an existing project* below: it changes what the steps do, and asks before every migration.

## Pre-flight

1. Confirm working directory with the user. Default = `$PWD`.
2. Detect what already exists:
   - `pyproject.toml` — read and preserve user values when adding tool sections.
   - `.git/` — only `git init` if missing.
   - `src/` and `tests/` directories.
   - `.gitignore`, `.pre-commit-config.yaml`, `uv.lock`.
3. Ask the user for:
   - **Package name** (kebab-case, e.g. `my-feature`).
   - **Project type** — it sets the defaults in the table below:
     - **Library:** imported by other code, published to PyPI.
     - **Application / service:** deployed and run — a web service, a worker, a desktop app.
     - **CLI:** a command-line tool, often published to PyPI.
     - **Scripts & data:** analysis, notebooks, automation that isn't distributed.
   - **Python versions.** The minimum goes in `requires-python`. A library supports every CPython still receiving security fixes ([python.org/downloads](https://www.python.org/downloads/)); an application can require just the version it's deployed on.
   - **Architecture style** — recorded as ADR-0001 (step 4):
     - **Simple modules** (default for CLIs and scripts & data): plain modules, no enforced layers.
     - **Layered:** e.g. `api` → `services` → `domain`, each layer importing only the ones below; enforced by import-linter.
     - **Hexagonal** (ports and adapters): a framework-free domain core, I/O in adapters at the edges, dependencies pointing inward; enforced by import-linter. Worth it for services with several I/O channels and real business logic.
   - **License** (default `MIT`).

| | Library | Application / service | CLI | Scripts & data |
|---|---|---|---|---|
| CI test matrix (`/env-ci-setup`) | every supported Python | the deployed Python | every supported Python | one Python |
| `py.typed` marker (PEP 561) | yes | — | — | — |
| `[project.scripts]` entry point | — | if it has a command | yes | — |
| Release workflow (`/env-ci-setup`) | GitHub release + PyPI | GitHub release, optional | GitHub release + PyPI, optional | none |
| Extra checks | — | container scan (trivy) if there's a Dockerfile | — | `nbstripout` pre-commit hook if there are notebooks |

## Adopting an existing project

When the project already has code (a `pyproject.toml`, `setup.py`, `setup.cfg`, or `requirements*.txt`, or Python files with history), adopt it instead of imposing the baseline. Work on a branch (`chore/adopt-workflow`), one commit per step, so each change can be reviewed and reverted on its own.

### A1. Detect what's there

| Concern | Look for |
|---|---|
| Package manager | `[tool.poetry]` / `poetry.lock`, `Pipfile`, `pdm.lock`, `requirements*.in` (pip-tools), `setup.py` / `setup.cfg`, `uv.lock` |
| Formatting and linting | `[tool.black]`, `[tool.isort]` / `.isort.cfg`, `[flake8]` in `setup.cfg` / `.flake8` / `tox.ini`, `[tool.pylint]` / `.pylintrc`, `[tool.ruff]` |
| Types | `[tool.mypy]` / `mypy.ini`, `[tool.pyright]` / `pyrightconfig.json` |
| Tests | the test runner and folder, current coverage, `tox.ini` / `noxfile.py` |
| Hooks and CI | `.pre-commit-config.yaml`, `.github/workflows/` |
| Repo hygiene | `.gitignore`, and generated files already committed: `git ls-files -ci --exclude-standard` once the baseline `.gitignore` is in place |

### A2. Propose an adoption plan, then ask

Show a table — each concern, what's there, and **keep**, **migrate**, or **add** — and get the user's go-ahead for each migration. Typical rows:

- **Poetry, Pipenv, PDM, or pip-tools → uv:** `uvx migrate-to-uv` converts the metadata to PEP 621 and dependency groups and writes `uv.lock`. It may switch the build backend (to Hatchling); confirm the built package didn't change by comparing the wheel's file list before (built with the old tool, at the pre-migration commit) and after (`uv build --wheel`), ignoring `.dist-info/`. Commit: `build: migrate from <tool> to uv`.
- **`setup.py` only:** move the metadata into `[project]` by hand, with the user; keep `setup.py` only if it runs build logic.
- **black, isort, flake8 → ruff:** carry over the line length from `[tool.black]`, isort's `known-first-party` into `[tool.ruff.lint.isort]`, and flake8 ignores that ruff implements; drop the old configs and dev dependencies. Ruff's formatter is black-compatible, so a black-formatted code base barely changes. If `ruff format` does rewrite many files, commit that alone (`style: format with ruff`) and add its hash to `.git-blame-ignore-revs` so `git blame` skips it.
- **pyright:** the workflow's hooks, stop gate, and CI use mypy. Run both if the team wants pyright; replacing mypy means adapting pre-commit and CI, and the stop gate then doesn't type-check.
- **tox or nox:** keep. They can call `uv run` too.
- **An existing `.pre-commit-config.yaml`:** merge — keep hooks for tools that stay, replace those for tools that were migrated.

### A3. Stop tracking generated files

Merge the step 5 entries into `.gitignore`, then untrack whatever git still tracks that's now ignored — committed `__pycache__/`, `.coverage`, build output:

```bash
git ls-files -ci --exclude-standard                          # review the list first
git ls-files -ci --exclude-standard -z | xargs -0 git rm --cached -q
git commit -m "chore: stop tracking generated files"
```

This matters beyond tidiness: running the tests rewrites tracked `.pyc` and `.coverage` files, and pre-commit fails any hook that modifies tracked files.

### A4. Ratchet strictness instead of breaking the build

The baseline's strict settings would fail an existing code base everywhere at once. Record today's state as a baseline instead, hold new code to the full standard, and let the baseline only shrink:

- **ruff:** `uv run ruff check --add-noqa .` marks each existing violation with a `# noqa: <codes>` comment; new code gets the full rule set. (If the team would rather not touch many files, use `[tool.ruff.lint.per-file-ignores]` for the worst files instead.) Commit: `chore: suppress existing lint findings`.
- **mypy:** keep `strict = true` and exempt the modules that fail today:
  ```bash
  uv run mypy src > mypy-baseline.log
  uv run python - <<'EOF'
  import re
  from pathlib import Path
  log = Path("mypy-baseline.log").read_text()
  modules = sorted({
      re.sub(r"/__init__$", "", path[len("src/"):-len(".py")]).replace("/", ".")
      for path in re.findall(r"^(src/[^:]+\.py):", log, re.M)
  })
  print("# Legacy baseline: modules that failed strict mypy when the workflow was adopted.")
  print("# Remove a module once it passes; never add new ones.")
  print("[[tool.mypy.overrides]]")
  print("module = [" + ", ".join(f'"{m}"' for m in modules) + "]")
  print("ignore_errors = true")
  EOF
  ```
  Append the printed block to `pyproject.toml` and delete the log. New modules are strict from day one. The trade-off: new errors *inside* a baseline module aren't reported until the module leaves the baseline — so when a task substantially changes one, fix its errors and remove it from the list.
- **Coverage:** set `fail_under` to today's coverage, rounded **down** from the exact value (the report's rounded percentage can be above it, which would fail at once):
  ```bash
  uv run pytest -q --cov --cov-branch --cov-fail-under=0
  uv run coverage json -q -o - | uv run python -c 'import json, math, sys; print(math.floor(json.load(sys.stdin)["totals"]["percent_covered"]))'
  ```
  Comment it as the adoption baseline, to raise as tests are added. In CI, `/env-ci-setup` adds a changed-lines coverage check, so every PR's new code meets the normal 85% even while the total is lower.

### A5. Continue with the steps below

Then run steps 1–9 with these differences: step 3 merges the tool sections into the existing `pyproject.toml` (with the ratchets above); step 4 creates only what's missing — `docs/` and ADR-0001 — and the smoke test only if there are no tests yet; step 9 is a series of commits on the adoption branch, opened as a PR for the team to review.

## Steps

### 1. Initialize git if missing

```bash
[[ -d .git ]] || git init -b main
```

### 2. Install or verify `uv`

```bash
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. `pyproject.toml` (PEP 621)

Generate or merge — never overwrite user fields:

```toml
[project]
name = "<package-name>"
version = "0.1.0"
requires-python = ">=3.12"
description = "..."
license = { text = "MIT" }
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
  "ruff>=0.6",
  "mypy>=1.11",
  "pytest>=8",
  "pytest-cov>=5",
  "pytest-xdist>=3",
  "hypothesis>=6",
  "pre-commit>=3.7",
  "import-linter>=2",  # Layered or hexagonal style only
  "bandit>=1.7",
  "pip-audit>=2.7",
]

[tool.ruff]
target-version = "py312"  # Match requires-python's minimum
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "C4", "SIM", "RUF"]
ignore = []

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"  # Match requires-python's minimum
strict = true
warn_unreachable = true
disallow_any_unimported = true

[tool.pytest.ini_options]
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
xfail_strict = true

[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
show_missing = true
skip_covered = false
fail_under = 85  # Enforced by pytest-cov in CI and /verify; adjust per project

# Layered or hexagonal style only:
[tool.importlinter]
root_packages = ["<package_name_underscored>"]
include_external_packages = true  # required to forbid third-party imports
# Contracts are added by the walking-skeleton task, from architecture.md.
```

Don't add contracts here: import-linter fails on a contract whose source module doesn't exist yet. With zero contracts, `lint-imports` passes. For the simple-modules style, leave out `[tool.importlinter]` and the `import-linter` dependency; `/env-ci-setup` then skips its Architecture job.

By project type:

- **Library:** add `src/<package_name_underscored>/py.typed` (empty) so type checkers use the package's annotations, and fill in `[project]` `authors`, `readme`, `classifiers` (including one `Programming Language :: Python :: 3.X` per supported version), and `[project.urls]` for PyPI.
- **CLI, or an application with a command:** add `[project.scripts]`, e.g. `<package-name> = "<package_name_underscored>.cli:main"`, with a `cli.py` whose `main()` returns an exit code.

If `pyproject.toml` already exists, **merge each section** rather than replace; ask before overwriting any user-set field.

### 4. Directory layout, ADR-0001, and workflow rules

```bash
mkdir -p src/<package_name_underscored> tests docs/workflow docs/adr
touch src/<package_name_underscored>/__init__.py tests/__init__.py
cat > tests/test_smoke.py <<'EOF'
import <package_name_underscored>


def test_package_imports() -> None:
    assert <package_name_underscored>.__name__ == "<package_name_underscored>"
EOF
```

The smoke test gives pytest something to collect from day one. With zero tests, pytest exits with code 5, which fails the pre-push hook and CI.

Record the architecture style as the project's first decision, `docs/adr/0001-architecture-style.md`:

```markdown
# 0001. Architecture style: <simple modules | layered | hexagonal>
Status: Accepted
Date: YYYY-MM-DD

## Context
<project type, what the code does, which I/O it has (HTTP, DB, queues, files, CLI)>

## Decision
<the style, and what it means here: the layers or the core/adapters split, and which imports are allowed>

## Consequences
<enforced by import-linter contracts added with each feature's walking skeleton | not enforced by tooling>.
A feature that needs a different structure gets its own ADR that says why.

## Alternatives considered
<the other two styles, and why not>
```

`/arch-plan` and the architect follow ADR-0001 for every feature.

Finally, make sure Claude loads the workflow's rules in this project. Claude Code reads every `.md` file in `.claude/rules/`, so the rules need no change to `CLAUDE.md` or `AGENTS.md`:

- If `.claude/rules/python-workflow.md` exists, leave it; `python-workflow install <project-dir>` put it there.
- Otherwise — the workflow is installed globally — copy it in:
  ```bash
  mkdir -p .claude/rules
  cp ".claude/python-workflow/templates/workflow-rules.md" .claude/rules/python-workflow.md
  ```
  Commit it with the project, so every teammate's Claude follows the same rules. `/env-doctor` reports when it falls behind the installed version.

### 5. `.gitignore`

Write a comprehensive Python `.gitignore` (or append missing entries if one exists). At minimum:

```
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.venv/
venv/
dist/
build/
*.egg-info/
.env
.envrc
# Per-task ephemeral state and task worktrees (written by /orchestrate)
.workflow/current-task.yaml
.worktrees/
uv.lock.bak
mutants/
```

`.gitignore` comments must be on their own line — a `#` after a pattern becomes part of the pattern, and the line silently matches nothing.

### 6. `.pre-commit-config.yaml`

```yaml
default_install_hook_types: [pre-commit, commit-msg, pre-push]
default_stages: [pre-commit]

repos:
  # Python tools run from the project's own environment, at the versions in
  # uv.lock: the same as CI, with the project's dependencies importable.
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run --frozen ruff check --fix --force-exclude
        language: system
        types_or: [python, pyi]
      - id: ruff-format
        name: ruff format
        entry: uv run --frozen ruff format --force-exclude
        language: system
        types_or: [python, pyi]
      - id: bandit
        name: bandit
        entry: uv run --frozen bandit -q
        language: system
        types: [python]
        files: ^src/  # Tests use assert by design
      - id: mypy
        name: mypy
        entry: uv run --frozen mypy src
        language: system
        pass_filenames: false
        types_or: [python, pyi]
        stages: [pre-push]
      - id: pytest
        name: pytest
        entry: uv run --frozen pytest -q -x
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.0.0  # Replaced by `pre-commit autoupdate` below
    hooks:
      - id: gitleaks

  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.0.0  # Replaced by `pre-commit autoupdate` below
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: [feat, fix, refactor, perf, docs, test, chore, build, ci, style, revert]

  # Scripts & data projects with notebooks only: strip outputs before committing.
  - repo: https://github.com/kynan/nbstripout
    rev: 0.9.0  # Replaced by `pre-commit autoupdate` below
    hooks:
      - id: nbstripout
```

What runs when: ruff, bandit, and gitleaks on every commit (fast); the Conventional Commits check on every commit message; mypy and the test suite on every push. Running Python tools through `uv run --frozen` keeps them in step with CI and gives mypy the project's dependencies — an isolated `mirrors-mypy` environment can't import them, and fails strict mode on every third-party import. Git hooks are shared by worktrees, and each task worktree has its own `.venv`, so the hooks work there too.

The hooks need `uv.lock` and the installed dev group, so they're installed after step 7.

### 7. Dependencies

```bash
uv sync --all-groups
uv run pre-commit autoupdate --repo https://github.com/gitleaks/gitleaks --repo https://github.com/compilerla/conventional-pre-commit  # Plus --repo https://github.com/kynan/nbstripout if used
uv run pre-commit install
```

This creates `.venv/` and `uv.lock`, pins the two remote hooks to their latest releases, and installs the pre-commit, commit-msg, and pre-push hooks.

### 8. Smoke test

```bash
uv run ruff check .
uv run mypy src
uv run pytest --collect-only
uv run lint-imports              # Layered or hexagonal style only
```

All should succeed; pytest collects the smoke test.

### 9. Initial commit (if git was just initialized)

Ask the user before committing. If yes:

```bash
git add .
git commit -m "chore: bootstrap project with workflow baseline"
```

Use Conventional Commits.

## Operating principles

- **Never destroy.** If `pyproject.toml` exists, merge into it. Ask before overwriting any user-set field.
- **Be explicit about what changed.** End with a summary table: file → action (created / merged / skipped).
- **Leave the project usable.** After this skill runs, `uv run pytest` should work and `pre-commit run --all-files` should pass.

## Exit criteria

- `uv run ruff check .` exits 0.
- `uv run mypy src` exits 0 (or the user has acknowledged stub warnings on an empty package).
- `uv run pytest --collect-only` exits 0.
- `pre-commit install` installed all three hook types (`.git/hooks/pre-commit`, `commit-msg`, `pre-push`).
- `docs/adr/0001-architecture-style.md` records the chosen style.
- A summary report listing every file created/modified, and the project type and style chosen.
- Adopted projects: the adoption plan with each row's outcome, and the size of each baseline (modules in the mypy baseline, `# noqa` count, coverage `fail_under`).

## After completion

Suggest next: **`/env-ci-setup`** to add GitHub Actions, then `/env-doctor` to verify the full baseline, then `/req-research` to start the first feature.
