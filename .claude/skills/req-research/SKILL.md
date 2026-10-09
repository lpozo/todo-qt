---
name: req-research
description: Phase 1 of the AI-assisted coding workflow — elicit requirements for a new feature. Use when starting a new feature, when the user describes what they want to build, or when /req-research is invoked. Produces docs/workflow/<slug>/requirements.md with Given/When/Then acceptance criteria.
---

# Phase 1 — Requirement Research

Your job: turn a raw user request into a clear `requirements.md`. The user, the spec author (Phase 2), and the verifier (Phase 8) will all read this artifact. It must be unambiguous.

## Inputs

- Raw request from the user (just received).
- Existing repo state — scan for prior art, similar features, conventions.

## Steps

1. **Confirm the slug and change type.** Ask the user for a kebab-case slug (e.g. `user-auth`) and the Conventional Commits type of the change (default `feat`; also `fix`, `refactor`, `perf`, `docs`, `test`, `chore`). All artifacts will live under `docs/workflow/<slug>/`.
2. **Start the branch** `<type>/<slug>` as described under *Git Workflow* in the workflow rules (`.claude/rules/python-workflow.md`). Halt if the working tree isn't clean — don't stash. If you're already on a branch other than the default one, ask whether to use it instead.
3. **Spawn the researcher subagent** to scan the codebase for:
   - Prior art (similar features, partial implementations).
   - Reusable utilities, helpers, base classes.
   - Existing conventions (logging, error handling, config patterns).
   - Constraints implied by the codebase (Python version, framework, deployment target).
   Use `Agent(subagent_type="researcher", ...)` with a focused prompt. Don't do this exploration in the main thread.
4. **Interview the user** to fill gaps. Ask, in order:
   - **Goal:** What outcome does the user/stakeholder need? Why now?
   - **Acceptance criteria:** "Given X, when Y, then Z" — at least one per behavior.
   - **Constraints:** performance, security, compat, deadline.
   - **Non-goals:** what is *explicitly* out of scope.
   - **Open questions:** anything you can't answer — assign owner + deadline.
   Use `AskUserQuestion` for multiple-choice clarifications; plain text for open ones.
5. **Apply MoSCoW** to acceptance criteria — mark each as Must / Should / Could / Won't. The Won't list IS the non-goals list.
6. **Use the Five Whys** if motivation is unclear. Don't accept "because the user said so" as the root cause.
7. **Validate INVEST** for any user-story-shaped items: Independent, Negotiable, Valuable, Estimable, Small, Testable.
8. **Write the artifact** to `docs/workflow/<slug>/requirements.md` from the template `.claude/python-workflow/templates/requirements.md`. Fill in every section, replacing the `<…>` guidance; the *Reuse Notes* come from the researcher's report.

## Exit criteria — do not advance until ALL hold

- No unresolved blocker-level questions (low-priority deferrals OK if owner+deadline assigned).
- Every acceptance criterion is in Given/When/Then form and individually testable.
- Non-goals list is non-empty (if everything is in scope, scope is wrong).
- The user has acknowledged the artifact.

## After writing

1. **Commit** the artifact: `git add docs/workflow/<slug>/requirements.md && git commit -m "docs(<slug>): add requirements"`.
2. **Offer a draft PR.** Ask the user; if they agree, `git push -u origin <branch>` and `gh pr create --draft` with the goal as the title (`<type>(<slug>): <goal>`) and a body that summarizes the acceptance criteria and links `docs/workflow/<slug>/`. Skip with a note if there's no remote or `gh`.
3. Report the path, a 1-line summary, and the PR URL if any. Suggest `/spec-write` next. Do **not** start writing the spec yourself.
