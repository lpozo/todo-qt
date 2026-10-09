---
name: quick-change
description: The quick track of the AI-assisted coding workflow — a bug fix or small change done test-first in one short loop, instead of the 8 phases. Use when the user reports a bug or asks for a small, well-understood change. Invoked by /quick-change. Produces brief.md, a failing regression test commit, the fix, and a PR verified by /verify.
---

# Quick Track — Bug Fixes and Small Changes

Your job: take a bug report or a small change request to a verified PR, with the regression test written — and seen failing — before the fix.

## 1. Check the change qualifies

The quick track fits when **all** of these hold:

- One behavior changes (one bug, or one small addition).
- Roughly 3 files or fewer, or about 150 changed lines, tests included.
- No new public interface, dependency, database schema, or migration.
- No architectural decision — nothing that would deserve an ADR.

If any doesn't hold, recommend the full track (`/req-research`) and say which criterion failed. The user decides; if they choose the quick track anyway, note their reason in the brief.

## 2. Start the branch

Follow *Git Workflow* in the workflow rules (`.claude/rules/python-workflow.md`): a clean working tree, then `<type>/<slug>` from the fresh default branch — usually `fix/<slug>` for a bug.

## 3. Write the brief

Write `docs/workflow/<slug>/brief.md` from `.claude/python-workflow/templates/brief.md`:

- **Problem.** For a bug, the steps to reproduce, the expected result, and the actual one. Reproduce it yourself first if you can; if you can't, say so and ask the user for what's missing rather than guessing.
- **Acceptance criteria.** One to three, in Given/When/Then form. For a bug, the first is the reproduction turned right: *Given the steps, When …, Then the expected result.*
- **Expected changes** and **out of scope.**

Show the brief to the user and get their confirmation. Then commit it — `docs(<slug>): add brief` — and offer a draft PR the same way `/req-research` does (ask first; `<type>(<slug>): <summary>` title).

## 4. Red: reproduce the problem in a test

1. Write the regression test — named for the behavior, e.g. `test_login_rejects_expired_token` — in the matching test file.
2. Run it: `uv run pytest <node id> -x`.
3. **Read the failure.** It must fail for the reported reason — the wrong result, the exception from the report — not an import error, a typo, or a missing fixture. If it fails for another reason, fix the test. If it passes, the reproduction is wrong; go back to the brief.
4. Record the node id under *Regression Test* in the brief.
5. Commit the test and the brief update **alone**, before any fix:
   ```bash
   git add <test file> docs/workflow/<slug>/brief.md
   git commit -m "test(<slug>): reproduce <the problem>"
   ```
   The pre-commit hooks don't run tests, so committing a failing test is fine. `/verify` checks out this commit and confirms the test failed there: it's the evidence that the test detects the problem.

## 5. Green, then refactor

Follow the green and refactor steps of `/tdd-cycle`: the minimum change that makes the regression test pass, then clean up with the tests green. Run the whole suite before committing — `uv run pytest -q` — since a fix can break neighbors. Stay within the brief's expected changes; if the fix needs more, stop and tell the user: the change may not qualify for the quick track anymore.

Commit: `fix(<slug>): <what changed>` (or the brief's type).

## 6. Verify and publish

Run `/verify`. On the quick track it reads `brief.md` instead of `requirements.md` and `spec.md`, and adds the red-first check on the `test(<slug>): reproduce` commit.

## What you must NOT do

- Fix before the failing test is committed.
- Commit the test and the fix together — that destroys the evidence.
- Grow the change past the quick-track criteria without telling the user.
- Skip `/verify` because the change is small.
