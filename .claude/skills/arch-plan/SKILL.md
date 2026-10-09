---
name: arch-plan
description: Phase 3 of the AI-assisted coding workflow — design how the spec lives in the codebase. Use after /spec-write, when spec.md exists and the user is ready to commit to module boundaries and library choices. Invoked by /arch-plan. Produces architecture.md plus ADR files.
---

# Phase 3 — Architectural Planning

Your job: decide *how* the spec's behaviors are organized in code — module boundaries, dependency direction, library choices — without writing any production code yet.

## Inputs

- `docs/workflow/<slug>/spec.md`
- Existing `pyproject.toml`, `src/` layout, prior ADRs in `docs/adr/` — above all `0001-architecture-style.md`, the project's chosen style.

## Steps

1. **Read the spec.** If it's incomplete (missing failure modes, no behavioral examples), halt and tell the user to revise.
2. **Spawn the architect subagent** with the spec + repo layout. The architect proposes the structure; you review.
3. **Follow the project's architecture style** from ADR-0001 (`docs/adr/0001-architecture-style.md`):
   - **Simple modules:** place the feature's code in clearly named modules; no layering rules, no import-linter contracts.
   - **Layered:** assign each new module to a layer; lower layers never import higher ones.
   - **Hexagonal:** a domain core with no framework imports or I/O; adapters for HTTP, DB, queues, CLI at the edges; adapters depend on the domain, never the reverse.

   Either way, the feature's code goes inside the project package — `src/<package>/<feature>/` by default — never into a new top-level package under `src/` (see *Placeholders* in the workflow rules, `.claude/rules/python-workflow.md`).

   If ADR-0001 is missing, halt and ask the user to choose a style (`/env-bootstrap` records it). If this feature genuinely needs a different structure, propose it as a new ADR that says why — don't drift silently.
4. **Capture irreversible decisions as ADRs.** One ADR per decision in `docs/adr/NNNN-title.md`. Format:
   ```markdown
   # NNNN. <title>
   Status: Accepted | Superseded by NNNN
   Date: YYYY-MM-DD
   ## Context
   ## Decision
   ## Consequences
   ## Alternatives considered
   ```
5. **Pick libraries** with one-line rationale per choice. Check `pyproject.toml` first — don't add a new dep when an existing one fits.
6. **Diagram if useful** — Mermaid sequence/component diagrams in the markdown. Skip if the structure is obvious.
7. **Define enforcement** (layered or hexagonal style) — write the import-linter contracts (TOML for `[tool.importlinter]` in `pyproject.toml`) into `architecture.md`'s *Architecture Enforcement* section, so the architecture is checked in CI, not just documented. Don't edit `pyproject.toml` here: a contract fails until its source module exists, so the walking-skeleton task adds the contracts together with the modules.
8. **Save** `docs/workflow/<slug>/architecture.md`, following the template `.claude/python-workflow/templates/architecture.md`. Its example rows show a hexagonal feature; replace them with the modules this feature needs, placed per ADR-0001. Omit *Architecture Enforcement* for the simple-modules style.

## Best practices

- **The style is a project decision, not a per-feature one.** ADR-0001 sets it; features follow it, or change it through a new ADR.
- **ADRs are immutable.** If a decision changes, write a new ADR that supersedes the old one.
- **C4 model for diagrams** — pick the level (Context, Container, Component, Code) that adds clarity. Don't draw all four by default.
- **Reuse before adding.** A new dependency is a long-term liability.

## Exit criteria

- Every behavioral example in the spec maps to an explicit module path.
- ADRs exist for every irreversible choice.
- Layered or hexagonal style: `architecture.md` contains import-linter contracts that encode the dependency direction.
- The user has acknowledged the artifact.

## After writing

**Commit** the artifact on the branch — `git commit -m "docs(<slug>): add architecture and ADRs"` — and `git push` if the branch has an upstream, so the draft PR shows it.

Report path + ADR list. Suggest `/impl-plan` next.
