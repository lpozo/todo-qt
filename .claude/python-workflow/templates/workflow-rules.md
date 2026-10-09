# Workflow Conventions for Claude

This repo (or a branch within it) is governed by the 8-phase AI-assisted coding workflow. When you operate here, follow these rules.

## Environment Setup (one-time)

Before running any workflow phase on a fresh repo, ensure the baseline is in place:

| Skill | When to run |
|---|---|
| `/env-bootstrap` | New project, or upgrading an existing project to the workflow baseline. Idempotent. |
| `/env-doctor` | Anytime you're unsure whether the project is workflow-ready. Read-only; reports missing pieces. |
| `/env-ci-setup` | After `/env-bootstrap`, before the first `/verify` run. Sets up `.github/workflows/ci.yml`. |

If `/env-doctor` reports critical items missing, stop and run `/env-bootstrap` before starting Phase 1.

## Cardinal Rules

1. **Phases produce named artifacts.** The hand-off is the artifact, not a conversation summary.
   - Phase 1 → `docs/workflow/<slug>/requirements.md`
   - Phase 2 → `docs/workflow/<slug>/spec.md`
   - Phase 3 → `docs/workflow/<slug>/architecture.md`
   - Phase 4 → `docs/workflow/<slug>/impl-plan.md`
   - Phase 5 → `docs/workflow/<slug>/tasks.yaml`
   - Quick track → `docs/workflow/<slug>/brief.md`
2. **Pick the track, then don't skip its steps.** Bug fixes and small changes — one behavior, ~3 files or fewer, no new public interface, dependency, schema, or migration — take the quick track (`/quick-change`): a brief, a failing regression test committed before the fix, then `/verify`. Everything else takes the 8 phases. Don't skip a phase or step without the user's explicit approval; if you think one should be skipped, say so and ask.
3. **One slash command per phase.** Use `/req-research`, `/spec-write`, `/arch-plan`, `/impl-plan`, `/task-define`, `/orchestrate`, `/tdd-cycle`, `/verify` — or `/quick-change` for the quick track. Don't reimplement them inline.
4. **Spawn the role-specific subagent for each phase.** The skills will do this for you; trust them.
5. **Respect the file allow-list.** When implementing a task, the `enforce_allowlist.py` hook blocks edits outside `.workflow/current-task.yaml`'s `files_in_scope`. If you genuinely need to touch another file, stop and redraw task boundaries — don't bypass the hook.

## Per-Phase Quick Reference

| Phase | What you do | What you must NOT do |
|---|---|---|
| 1 Requirements | Interview, scan codebase, write `requirements.md` with Given/When/Then acceptance criteria | Skip user clarification; assume motivation |
| 2 Spec | Define interfaces, schemas, behavioral examples | Smuggle implementation choices into the spec |
| 3 Architecture | Module decomposition in the style of ADR-0001, ADRs for irreversible choices | Pick libraries before checking what's already in `pyproject.toml` |
| 4 Impl Plan | Ordered file list, test list, reuse pointers | Re-derive architecture; reuse Phase 3's output |
| 5 Task Definition | Cut tasks with non-overlapping `files_in_scope` allow-lists | Create tasks that share files |
| 6 Orchestration | Dispatch tasks; conductor merges | Conductor edits code itself |
| 7 TDD | Red → Green → Refactor inside one task | Refactor in green step; add features in refactor step |
| 8 Verify | Run full toolchain, cross-check acceptance criteria | Skip integration tests because units pass |

## Toolchain Defaults

- **Env / deps:** `uv` (lockfile-native; manages Python versions). For one-off scripts, use PEP 723 inline metadata + `uv run script.py`.
- **Lint / format:** `ruff` (replaces black, isort, flake8, pyupgrade).
- **Types:** `mypy` with `[tool.mypy] strict = true` set in `pyproject.toml`. Skills and hooks invoke bare `mypy src` and let the config enforce strictness — don't pass `--strict` on the command line.
- **Tests:** `pytest` + `pytest-xdist` + `pytest-cov` (branch on). Property-based via `hypothesis`. Real services via `testcontainers`.
- **Security:** `bandit`, `pip-audit`, `gitleaks` on every PR.
- **Pre-commit:** mirrors CI locally, with tools run via `uv run --frozen` at the `uv.lock` versions. Commit: ruff, bandit, gitleaks. Commit message: Conventional Commits check. Push: mypy, pytest.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).

## Subagent Roster

Spawned automatically by the skills. Each has a narrow role and tool set:

- `researcher` — codebase exploration, prior-art discovery (read-only).
- `spec-author` — writes `spec.md` from `requirements.md`.
- `architect` — writes `architecture.md` from `spec.md`.
- `planner` — writes `impl-plan.md` from spec + architecture.
- `task-cutter` — writes `tasks.yaml`; validates DAG.
- `test-writer` — writes failing tests for one task (red step).
- `implementer` — makes failing tests pass (green + refactor).
- `reviewer` — fresh-eyes diff review with no planning context.

## Repo Layout Expectations

```
<project>/
│
├── .workflow/
│   └── current-task.yaml  ← Active task contract, in task worktrees only (ignored by git)
│
├── docs/
│   │
│   ├── adr/  ← Architecture Decision Records (one per file)
│   │
│   └── workflow/
│       │
│       └── <slug>/  ← Per-change artifacts
│           ├── architecture.md
│           ├── brief.md
│           ├── impl-plan.md
│           ├── requirements.md
│           ├── spec.md
│           └── tasks.yaml  ← Phase 5 output, checked by validate_tasks.py
│
├── src/
│   │
│   └── <package>/  ← The project's one package; features live inside it
│
├── tests/  ← Test suite mirroring the package
│
└── pyproject.toml  ← PEP 621 metadata + tool configs (ruff, mypy, pytest, coverage, importlinter)
```

**Placeholders in the skills and templates:**

- `<slug>` names the change, in kebab-case (`user-auth`): the branch, `docs/workflow/<slug>/`, commit scopes.
- `<package>` is the project's import package, the one directory under `src/` (`myapp`).
- `<feature>` is the slug's snake_case form (`user_auth`).

**Feature code goes inside the project package**, never into a new top-level package under `src/`: by default `src/<package>/<feature>/`, tested in `tests/<feature>/` (with an `__init__.py`, so test files with the same name in different features don't clash). The architect may place it differently to follow ADR-0001 — a single module `src/<package>/<feature>.py` for a small feature, or one module per layer such as `src/<package>/domain/<feature>.py`. import-linter's `root_packages` stays `[<package>]`.

## Git Workflow

- **One branch per change, started in Phase 1** by `/req-research`. Name it `<type>/<slug>`, where `<type>` is the change's Conventional Commits type: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, or `chore`. Branch from the default branch, fresh from the remote if there is one:
  ```bash
  git fetch origin                     # skip if there's no remote
  base=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo main)
  git switch --no-track -c <type>/<slug> "$base"
  ```
  `--no-track` matters: without it the branch tracks the default branch, so a bare `git push` fails and "has an upstream" is wrongly true before the PR exists.
  Never commit workflow artifacts or code directly to the default branch.
- **Each phase commits its artifact** on the branch: `docs(<slug>): add requirements`, `… add spec`, `… add architecture and ADRs`, `… add implementation plan`, `… add task definitions`. A later revision is a new commit, e.g. `docs(<slug>): revise spec for <reason>`.
- **Draft PR after Phase 1.** Ask the user before the first push; then `git push -u origin <branch>` and `gh pr create --draft`. From then on, push after each phase's commit so reviewers see the artifacts in the PR as they land — that review is the human approval step between phases. Without a remote or `gh`, skip this and say so.
- **PRs are squash-merged**, so the PR title becomes the one commit on the default branch: it must be a Conventional Commit (`<type>(<slug>): <summary>`, checked in CI). Keep it accurate as the change evolves.
- **Task branches and worktrees** (`task/<task-id>`, `.worktrees/<task-id>`) belong to `/orchestrate`: created and deleted per task, never pushed.
- **Before publishing, `/verify` rebases** on the latest default branch, reruns the checks, and pushes with `git push --force-with-lease`, which refuses if someone else pushed in the meantime.
- **Never** force-push without `--force-with-lease`, rewrite the default branch, or delete branches you didn't create.

## When Things Go Wrong

- **Hook blocks a legitimate edit:** Don't bypass — fix the task boundary in `tasks.yaml` and update `.workflow/current-task.yaml`.
- **Acceptance test fails after green step:** Stay in green; do not refactor until green again.
- **Spec ambiguity surfaces during implementation:** Stop, update `spec.md`, re-run from Phase 4 for the affected slice. Don't improvise silently.
- **Reviewer agent flags an issue:** Treat as authoritative unless you can articulate why it's wrong.
