---
name: tdd-cycle
description: Phase 7 of the AI-assisted coding workflow — execute one task via red/green/refactor TDD inside a task worktree. Use when an implementer subagent is working on a single task with a known acceptance command; /quick-change also follows its green and refactor steps. Invoked by /tdd-cycle or by the orchestrator. Produces commits on the task branch.
---

# Phase 7 — TDD Cycle (one task)

(On the quick track, `/quick-change` borrows the green and refactor steps below; it works in the main checkout, without a task contract.)

You are the **implementer** for a single task. You work inside one git worktree — `cd` into it before anything else; the stop gate finds your task contract from your working directory. The `enforce_allowlist.py` hook will block any edit outside `.workflow/current-task.yaml`'s `files_in_scope` — respect it; do not bypass it.

## Inputs

- `.workflow/current-task.yaml` — task contract (id, files_in_scope, depends_on, acceptance, role, base_ref).
- `docs/workflow/<slug>/spec.md` — read-only reference for behavioral examples.

## The cycle (loop until acceptance passes)

### Red — write the failing test

1. Open the test file from `files_in_scope`.
2. Write the test corresponding to the spec's behavioral example.
3. Use **Arrange-Act-Assert** structure with one logical assertion per test.
4. Test name = behavior sentence: `test_user_lookup_returns_none_for_unknown_id`.
5. Run the test:
   ```bash
   <acceptance command>
   ```
6. **Read the failure message.** Confirm it failed for the spec'd reason — not a typo, import error, or missing fixture. If it failed for the wrong reason, fix the test.

### Green — minimum production code to pass

1. Open the production file from `files_in_scope`.
2. Write **the minimum code** to make the failing test pass.
3. **No extra abstractions.** No "while I'm here" refactors. No speculative features.
4. Run the test again. If still red, iterate — but only the minimum.
5. If multiple tests are green, stop. Don't write code beyond what tests demand.

### Refactor — clean up with green tests

1. Improve names, remove duplication, extract helpers.
2. Run the full task acceptance command after **every** change.
3. Stop when the code is *clean enough*, not perfect.
4. **Do NOT add features in this step.** If you find missing behavior, that's a new task, not this one.

## Tool conventions

- **Tests:** `pytest` + `pytest-cov` (branch coverage on).
- **Property-based:** `hypothesis` for invariant tests.
- **Time:** `freezegun`. **HTTP:** `respx` (httpx) or `responses` (requests). **Fixtures:** `factory_boy` / `polyfactory`. **Snapshots:** `syrupy`.
- **Format:** the post-edit hook runs `ruff format` automatically; don't fight it.

## Commit discipline

- One commit at the end of the cycle (red, green, and refactor squashed).
- **Conventional Commits**: `feat(<slug>): <task description>` or `test(<slug>): ...` if test-only.
- The orchestrator will squash-merge this into the change's branch — your commit message becomes the merge message.

## Exit criteria

- Acceptance command exits 0.
- `git diff --name-only` is a subset of `files_in_scope`.
- ruff and mypy report nothing in the files you changed (mypy inherits `[tool.mypy] strict = true` from `pyproject.toml`) — the stop gate will block you otherwise.
- No `print()`, `breakpoint()`, or commented-out code in the diff.

## After completion

Return control to the orchestrator (Phase 6). Do **not** start the next task.
