---
name: task-define
description: Phase 5 of the AI-assisted coding workflow — cut the impl plan into agent-executable tasks with non-overlapping file allow-lists. Use after /impl-plan, when impl-plan.md exists. Invoked by /task-define. Produces tasks.yaml — the most leveraged artifact for orchestration quality.
---

# Phase 5 — Task Definition

Your job: cut `impl-plan.md` into discrete tasks that agents can execute independently. **Boundary quality here determines orchestration success.**

## Inputs

- `docs/workflow/<slug>/impl-plan.md`

## Steps

1. **Read the impl plan.** Halt if missing or stale.
2. **Spawn the task-cutter subagent** with the plan. The cutter proposes the task list; you validate the DAG.
3. **Cut tasks** so that:
   - Each task has a **non-overlapping** `files_in_scope` allow-list. If two tasks need to touch the same file, redraw boundaries (often: extract a shared scaffolding task that runs first).
   - **Shared files go to the skeleton task**, T-00, which runs first: `pyproject.toml` and `uv.lock` together (every new dependency in the plan), shared `conftest.py` fixtures, and package `__init__.py` files. If a later task still needs one — a dependency nobody foresaw — it depends on the last task that changed that file, so they never run in parallel. No task owns `CHANGELOG.md`: `/verify` writes it.
   - Each task has **one acceptance command** that exits 0/non-zero.
   - Tasks are sized so an implementer agent can execute one in a single turn (~1–5 files, ~50–300 LOC).
4. **Build the DAG** — explicit `depends_on` edges. Topologically sort to find parallel layers.
5. **Save** to `docs/workflow/<slug>/tasks.yaml`, following the template `.claude/python-workflow/templates/tasks.yaml`; its header comment documents each field. The first task is the walking skeleton from the plan's Slice 0.
6. **Validate** with the workflow's checker, and fix every problem it reports until it passes:
   ```bash
   uv run --script ".claude/python-workflow/scripts/validate_tasks.py" docs/workflow/<slug>/tasks.yaml
   ```
   It checks the JSON Schema (`.claude/python-workflow/templates/tasks.schema.json`), unique ids, dependencies that exist, cycles, paths written as exact repo-relative files, files shared by two tasks in the same layer, and `CHANGELOG.md` in any task. It warns when `pyproject.toml` and `uv.lock` aren't in scope together. On success it prints the layers — the tasks `/orchestrate` will run in parallel.

> **Conflict resolution:** if two tasks both need the same file — say `domain.py` — either (a) sequence them so they run serially with `depends_on`, or (b) split the file into smaller modules so each task owns one. Never run two parallel tasks against the same file.

## Best practices

- **INVEST per task** — Independent (no shared files with parallel siblings), Negotiable (you can defer it), Valuable (delivers a slice), Estimable (clear scope), Small (~1 turn), Testable (one acceptance command).
- **Topological layers = parallelism.** Tasks at the same DAG depth run in parallel.
- **Allow-lists are mechanical** — the `enforce_allowlist.py` hook reads from `.workflow/current-task.yaml` and blocks edits outside scope. No convention required.
- **Validate mechanically, twice.** `validate_tasks.py` runs here, and `/orchestrate` runs it again before dispatching anything, since `tasks.yaml` may be edited in between.

## Checks the script can't make

- [ ] Every behavioral example from `spec.md` is covered by at least one task's tests.
- [ ] Each task fits one implementer turn (~1–5 files, ~50–300 LOC).
- [ ] Each acceptance command runs only the task's own tests.

## Exit criteria

- Two agents executing parallel tasks cannot produce a merge conflict (proven by allow-list disjointness).
- The user has acknowledged the artifact.

## After writing

**Commit** the artifact on the branch — `git commit -m "docs(<slug>): add task definitions"` — and `git push` if the branch has an upstream, so the draft PR shows it.

Report task count, parallel-layer count, and total estimated turns. Suggest `/orchestrate` next.
