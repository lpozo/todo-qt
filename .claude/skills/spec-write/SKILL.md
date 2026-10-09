---
name: spec-write
description: Phase 2 of the AI-assisted coding workflow — write a technical specification (SDD) from requirements. Use after /req-research, when requirements.md exists and the user is ready to pin down interfaces, schemas, and behaviors. Invoked by /spec-write. Produces spec.md.
---

# Phase 2 — Specification (SDD)

Your job: turn `requirements.md` into a `spec.md` precise enough that a test author could write the test suite without asking the implementer questions.

## Inputs

- `docs/workflow/<slug>/requirements.md` — must already exist. If missing, halt and tell the user to run `/req-research` first.

## Steps

1. **Read `requirements.md` completely.** If acceptance criteria are vague or missing Given/When/Then form, halt and ask the user to revise — do not paper over gaps.
2. **Confirm the feature slug** with the user if ambiguous.
3. **Spawn the spec-author subagent** with the full requirements content. The subagent writes the spec; you review and merge.
4. **Verify the draft** before saving. The spec must include, for every Must/Should acceptance criterion:
   - **Public interface signature** — function, endpoint, CLI, or class shape (with types).
   - **Pre-conditions** — what must be true of inputs.
   - **Post-conditions** — what is true of outputs/state after success.
   - **Failure modes** — what raises, what returns sentinel values, retry semantics.
   - **Behavioral examples** — at least one Given/When/Then row showing concrete inputs → outputs.
5. **Type-check the spec stubs.** If the spec includes Python type signatures, copy them into a scratch stub file and run `uv run mypy <stub file>` from the project root — the project's config makes it strict — to catch inconsistencies before they become test failures in Phase 7.
6. **Save** to `docs/workflow/<slug>/spec.md`, following the template `.claude/python-workflow/templates/spec.md`: one *Public Interfaces* entry per interface, each with its behavioral examples, and *Out of Scope* copied verbatim from the requirements' non-goals.

## Best practices

- **Design by contract.** Pre/post-conditions are not optional.
- **Make illegal states unrepresentable** — encode constraints in types (Pydantic v2, `Literal`, `NewType`), not runtime asserts.
- **Each behavioral example becomes a test** in Phase 7. Name them descriptively.
- **Specify failure modes loudly.** "Raises X when Y" beats "may raise an exception."

## Exit criteria

- Every Must/Should criterion in `requirements.md` maps to at least one public interface in the spec.
- A test author could write Phase 7's tests from the spec alone.
- Type signatures pass mypy with the project's strict config.
- The user has acknowledged the artifact.

## After writing

**Commit** the artifact on the branch — `git commit -m "docs(<slug>): add spec"` — and `git push` if the branch has an upstream, so the draft PR shows it.

Report path + summary. Suggest `/arch-plan` next.
