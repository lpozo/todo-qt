---
name: impl-plan
description: Phase 4 of the AI-assisted coding workflow — translate architecture into a concrete, ordered coding sequence. Use after /arch-plan, when architecture.md and spec.md exist and the user is ready to plan the actual coding work. Invoked by /impl-plan. Produces impl-plan.md.
---

# Phase 4 — Implementation Plan

Your job: produce an ordered list of concrete code changes that an implementer (or task-cutter in Phase 5) can execute mechanically.

## Inputs

- `docs/workflow/<slug>/spec.md`
- `docs/workflow/<slug>/architecture.md`
- Repo state — for identifying reuse opportunities.

## Steps

1. **Read both inputs.** Halt if either is missing or stale.
2. **Spawn the planner subagent** with both artifacts. The planner drafts the change list; you review.
3. **Order using a walking skeleton**:
   - First slice: thinnest possible end-to-end path (smoke-test that everything wires up). It also takes every change to files the later slices share — all new dependencies (`pyproject.toml` and `uv.lock`), shared fixtures (`conftest.py`), package `__init__.py` files — so Phase 5 can give them to one task that runs first.
   - Then: vertical slices by behavioral example, never horizontal layers.
   - Within a slice: data models → core domain → adapters → entry points.
4. **One test per behavioral example.** Copy the test name from the spec's behavioral examples table; the implementer in Phase 7 will write the actual test body.
5. **Identify reuse explicitly.** For each new file, list any existing helpers/utilities/base classes that should be used (with file paths). Reuse-before-create is a hard rule, not a suggestion.
6. **Build the dependency graph** — which files depend on which, in change-order terms.
7. **Save** `docs/workflow/<slug>/impl-plan.md`, following the template `.claude/python-workflow/templates/impl-plan.md`: the walking skeleton as Slice 0, then one section per slice, the dependency graph, the files in change order, the test list, and the reuse inventory.

## Best practices

- **Walking skeleton first.** Resist the urge to flesh out one layer fully before connecting end-to-end. The skeleton catches integration mismatches early.
- **Vertical slices.** Each slice should leave the system in a working state, even if behavior is incomplete.
- **Test name in plan = test body in Phase 7.** Don't invent new test names later.
- **Right-size slices.** A slice should be ~1–4 file changes. Bigger → split. Smaller → merge.

## Exit criteria

- Every behavioral example in the spec maps to a slice.
- Each slice item is small enough that an implementer wouldn't need to re-plan mid-task.
- Reuse inventory is non-empty (or you've explicitly verified nothing reusable exists).
- The user has acknowledged the artifact.

## After writing

**Commit** the artifact on the branch — `git commit -m "docs(<slug>): add implementation plan"` — and `git push` if the branch has an upstream, so the draft PR shows it.

Report path + slice count. Suggest `/task-define` next.
