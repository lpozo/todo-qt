---
name: env-doctor
description: Diagnose a Python project's compliance with the workflow baseline. Reports missing tools, missing pyproject sections, broken pre-commit, missing CI, a failing import-linter setup, a missing .gitignore setup, and an outdated workflow install. Outputs a checklist with copy-paste fix commands. Read-only — never modifies the project.
---

# env-doctor — Workflow baseline diagnostic

Your job: produce a **read-only** report on what the project has and what it's missing relative to the workflow baseline. Do **not** make changes — that's `/env-bootstrap`'s job.

## 1. Run the checks

From the project root:

```bash
uv run --script ".claude/python-workflow/scripts/doctor.py"
```

The script makes every mechanical check and changes nothing — it runs the tools in check-only mode with their caches off, and never syncs the environment. Each failure carries a severity (critical, important, nice) and a fix. It exits 1 if anything failed. Add `--no-smoke` to skip running the tools when you only need the configuration checks.

What it covers:

| Section | Checks |
|---|---|
| Runtime | uv and git available; inside a git repository |
| Project metadata | `pyproject.toml` with `[project]`, `requires-python` and a matching Python, the dev group; `uv.lock` present and current |
| Layout | `src/`, `tests/`, `docs/workflow/`; ADR-0001 names one style; git ignores `.workflow/current-task.yaml`, `.worktrees/`, `.venv/`, `__pycache__/`, `mutants/` |
| Tool configs | `[tool.ruff]`, strict mypy, pytest, branch coverage with `fail_under`, `[tool.importlinter]` for the layered and hexagonal styles |
| Pre-commit | the config's local hooks run via `uv run --frozen`; gitleaks; Conventional Commits at commit-msg; git hooks installed |
| CI | `ci.yml` exists and runs ruff, mypy, and pytest |
| Workflow bundle | python-workflow installed (project or global); its hooks registered; `.claude/rules/python-workflow.md` present and matching the installed version |
| Adoption baselines | informational: modules exempt from strict mypy, `# noqa` count, the coverage floor; a changed-lines coverage job when the floor is below 85 |
| Smoke | `ruff check .`, `ruff format --check .`, `mypy src`, `pytest --collect-only`, and `lint-imports` if configured |

## 2. Judge what the script can't

Read these yourself and add any finding to the report, as *important* unless it blocks work:

- **CI content.** The script only checks that `ci.yml` mentions the tools. Read it: are there jobs for lint, types, tests, and security, with actions pinned to commit SHAs? If not, suggest `/env-ci-setup`.
- **ADR-0001 fits the project.** A hexagonal style in a 200-line script, or simple modules in a growing service with a database and an HTTP API, deserves a remark — the user decides.
- **Baselines shrinking.** If the project was adopted, compare the baseline numbers with the previous report if you have one. They should only go down.

## 3. Report

Turn the script's output into this report. Keep its severities; quote its fix commands, expanded into literal text to paste where that helps (the TOML for a missing section, the `.gitignore` lines).

```markdown
# Workflow Baseline Diagnostic — <project name>

Date: YYYY-MM-DD
Checks: 41 passed, 3 failed

## Critical (blocks /req-research)
- [ ] `.worktrees/` isn't ignored by git — add it to `.gitignore`

## Important (degrades the workflow)
- [ ] `.claude/rules/python-workflow.md` is older than the installed version — rerun `python-workflow install .`
- [ ] CI actions aren't pinned to commit SHAs — run `/env-ci-setup`

## Nice-to-have
- [ ] (none)

## Adoption baselines
- Modules exempt from strict mypy: 4
- Coverage floor: 61.5 (target 85)

## Suggested next step
Fix the critical item, then run `/req-research` to start the first feature.
```

## Operating principles

- **Read-only.** Never edit. Tell the user what to run.
- **The script's verdicts stand.** Don't re-check by hand what it already checked, and don't soften a failure.
- **Don't grade the project.** Report state; the user decides priorities.

## Exit criteria

- The script ran, with smoke checks unless the user asked to skip them.
- The report has the three severity sections, even if empty, and a clear next step.

## After completion

If critical items are present, suggest `/env-bootstrap`. If only CI is missing, suggest `/env-ci-setup`. If everything is green, suggest `/req-research` to start the first feature.
