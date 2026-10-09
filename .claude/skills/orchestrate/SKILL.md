---
name: orchestrate
description: Phase 6 of the AI-assisted coding workflow — execute tasks.yaml by dispatching subagents in topological layers. Use after /task-define, when tasks.yaml is validated and ready for execution. Invoked by /orchestrate. Acts as conductor — never edits code itself.
---

# Phase 6 — Implementation Orchestration

You are the **conductor**. You dispatch tasks to subagents, validate their output, and merge. **You do not write code.**

## Inputs

- `docs/workflow/<slug>/tasks.yaml`, from `/task-define`.

## Pre-flight (feature scaffolding + safety checks)

This phase is the first one that writes code, so it bears the responsibility of making the repo ready:

1. **Validate `tasks.yaml` again** — it may have been edited since Phase 5:
   ```bash
   uv run --script ".claude/python-workflow/scripts/validate_tasks.py" docs/workflow/<slug>/tasks.yaml
   ```
   Halt on any problem it reports. On success it prints the layers; the execution loop below runs them in that order.
2. **Confirm the working tree is clean** (`git status --porcelain` empty). If not, halt — don't auto-stash.
3. **Confirm you're on the change's branch.** `/req-research` started it (see *Git Workflow* in the workflow rules, `.claude/rules/python-workflow.md`). Take its name from `git branch --show-current` — below, `<branch>`. Halt if it's the default branch, or if `docs/workflow/<slug>/tasks.yaml` isn't committed on it.
4. **Confirm no leftover `.workflow/current-task.yaml`** in the main checkout; if present, halt and ask.
5. **Confirm `.worktrees/` is ignored:** `git check-ignore -q .worktrees/`. If not, halt and suggest adding it to `.gitignore` (`/env-bootstrap` does).
6. **Resume, don't restart.** Tasks already merged carry a `Task:` trailer on `<branch>`:
   ```bash
   git log --format='%(trailers:key=Task,valueonly)' <base>..<branch>   # <base>: the default branch
   ```
   Skip those tasks. If `git worktree list` shows leftover `.worktrees/` entries or `git branch --list 'task/*'` shows task branches, list them and ask the user whether to resume them or remove them — never delete them on your own.
7. **Check the baseline:** `uv run --script ".claude/python-workflow/scripts/doctor.py" --no-smoke`. Halt on any *critical* failure and suggest the fix it prints (often `/env-bootstrap`); mention the others to the user, but they don't block.

If any check fails, halt and tell the user.

## Execution loop

For each topological layer (tasks with dependencies all satisfied):

1. **Create one git worktree per task** in the layer, from `<branch>` as it is now (after the previous layer merged), and give it its own environment — the stop gate runs tools from the worktree's `.venv/bin`:
   ```bash
   git worktree add .worktrees/<task-id> -b task/<task-id> <branch>
   uv sync --frozen --directory .worktrees/<task-id>
   ```
   Use plain `git worktree`, not the Agent tool's `isolation` option: the worktree's location, branch, and starting commit must be exactly these.
2. **Extract the task contract** from `tasks.yaml` and write it as a **flat, single-task YAML** to each worktree's `.workflow/current-task.yaml`. This is the shape the hooks expect — they read `files_in_scope` and `acceptance` directly from the top level, not nested under `tasks[].`. Example transform — given this entry in `tasks.yaml`:
   ```yaml
   - id: T-01-domain-create
     description: Domain create()
     role: implementer
     files_in_scope: [tests/<feature>/test_domain.py, src/<package>/<feature>/domain.py]
     depends_on: [T-00-skeleton]
     acceptance: pytest tests/<feature>/test_domain.py -x
   ```
   Write to `<worktree>/.workflow/current-task.yaml`:
   ```yaml
   id: T-01-domain-create
   description: Domain create()
   role: implementer
   files_in_scope:
     - tests/<feature>/test_domain.py
     - src/<package>/<feature>/domain.py
   depends_on: [T-00-skeleton]
   acceptance: pytest tests/<feature>/test_domain.py -x
   base_ref: <commit the task branch starts from>
   ```
   Add `base_ref` — the full SHA of the commit the task branch was created from (`git -C .worktrees/<task-id> rev-parse HEAD` right after creating it). The stop gate diffs against it to catch out-of-scope changes even after they're committed; use a SHA, not a branch name, because `<branch>` moves while tasks run. Create `.workflow/` in the worktree first if it doesn't exist. You may rewrite a contract from the main checkout (e.g. to re-dispatch with a corrected scope); the task's agent can't.
3. **Dispatch a subagent per task in parallel** — one Agent tool call per task, all in the same message. The agent's `subagent_type` matches the task's `role` field (default `implementer`). The implementer runs the TDD cycle inside its worktree:
   ```
   Agent(
     subagent_type="implementer",
     description="<task id>",
     prompt="Work in <absolute path to .worktrees/<task-id>>: cd there before anything else.
             <task description, files_in_scope, acceptance command>"
   )
   ```
   The `cd` matters: the stop gate finds the task contract from the agent's working directory. (Edits are checked against the worktree's contract wherever the agent's shell is.)
   **Optional advanced split:** for high-stakes tasks, dispatch a `test-writer` first (red step only), wait for it to commit failing tests, then dispatch an `implementer` with the same `current-task.yaml` to do green + refactor. Independent test authorship is a stronger guarantee than a single-agent cycle. Use this when the cost of a missed bug exceeds the cost of two agent turns.
4. **Wait for all tasks in the layer** to return.
5. **Validate each task's output**:
   - Run the task's `acceptance` command in its worktree, with its environment: `uv run --frozen --directory .worktrees/<task-id> -- <acceptance>`.
   - Check `git -C <worktree> diff --name-only --no-renames <base_ref>` plus untracked files against `files_in_scope` — if any file outside scope was touched, **reject** the task and re-dispatch.
   - Don't trust the agent's own report that it's done: the stop gate lets an agent stop after 3 failed attempts in a row, with a warning.
6. **Spawn the reviewer subagent** with the diff (no planning context). The reviewer's verdict is authoritative unless you can articulate why it's wrong.
7. **Merge in topological order** into `<branch>`, from the main checkout. `git merge --squash` only stages the changes — it never commits, and ignores `-m` — so commit explicitly, with a Conventional Commits subject and a `Task:` trailer (used to resume an interrupted run):
   ```bash
   git merge --squash task/<task-id>
   git commit -m "feat(<slug>): <task description>" -m "Task: <task-id>"
   ```
8. **Tear down** the worktree and the task branch. `-D` is required: after a squash merge, git doesn't consider the branch merged.
   ```bash
   git worktree remove .worktrees/<task-id>
   git branch -D task/<task-id>
   ```

When all layers are complete, advance to Phase 8 (`/verify`).

## Subagent roles (for this phase)

- **implementer** — default. Writes tests AND code inside one task worktree, executing the `/tdd-cycle` (red → green → refactor) end-to-end.
- **test-writer** — *optional* split partner for `implementer`. Writes failing tests only (red step), then hands off. Use only when independent test authorship is worth the extra turn.
- **reviewer** — fresh-eyes diff review. Spawned with no prior context.

## Best practices

- **You never edit code.** If a task fails, redispatch — do not "just fix it."
- **Reviewer cold-start.** The reviewer agent must NOT see the planning context. Pass only the diff and the relevant task spec.
- **No rebasing in the normal flow.** Each layer's worktrees are created from `<branch>` after the previous layer merged, so they start current. Tasks in the same layer have disjoint `files_in_scope`, so their squash merges don't conflict.
- **Stop on failure.** If a task fails twice with the same root cause, halt and ask the user — don't loop forever.

## Exit criteria

- Every task in `tasks.yaml` has a green acceptance command.
- No task touched files outside its allow-list (verified by hook + post-hoc `git diff --name-only`).
- Reviewer signed off on every diff.
- `<branch>` contains one Conventional Commit per task, each with a `Task:` trailer.
- No `.worktrees/` entries or `task/*` branches left behind.

## After execution

Push `<branch>` if it has an upstream. Report a task-by-task results table. Suggest `/verify` next.
