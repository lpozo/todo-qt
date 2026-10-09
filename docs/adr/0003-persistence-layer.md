# 0003. Add a `persistence` layer beside `ui` (amends ADR-0001)
Status: Accepted
Date: 2026-10-09

## Context
ADR-0001 defines `ui` -> `services` -> `domain` with `cli` as composition root, but does not say
where persistence lives. The `task-list` spec puts the persistence port (`PlanStore`) and its
errors (`StoreError`, `StoreCorruptError`, `StoreWriteError`) in `todo_qt.services`, and requires
that `services` and `domain` do no I/O (clock, ids, and the data location are injected). Something
must implement the port with real file I/O. It cannot be `domain` (framework- and I/O-free),
`services` (would break its testability and the spec's "services imports only domain"), or `ui`
(the store has nothing to do with Qt, and the UI must not own storage).

## Decision
Add one layer, `todo_qt.persistence`, an adapter that implements `PlanStore`:

```
cli
ui | persistence      (siblings: neither may import the other)
services
domain
```

- `persistence` may import `services` (the port and the `Store*Error` classes it must raise) and
  `domain` (to build and validate `Plan`). It must not import `ui`, `cli`, or any Qt binding.
- `ui` and `persistence` are *independent* siblings; only `cli` (the composition root, as in
  ADR-0001) sees both and injects the concrete store into `PlanService` through the port.
- `services` owns the port (dependency inversion): it knows only the `PlanStore` Protocol.
- Everything in ADR-0001 otherwise stands (Qt only in `ui`; `domain` imports nothing).

This amends, and does not supersede, ADR-0001: the three original layers and their rules are
unchanged; a fourth, I/O-only layer is added next to `ui`. The persistence-specific stdlib I/O
(`json`, `os`) is allowed only there (and `cli`).

## Consequences
- Two import-linter contracts encode this: a layers contract with `ui | persistence` as sibling
  layers, and forbidden contracts that keep Qt and file I/O out of `domain` and `services`
  (see `docs/workflow/task-list/architecture.md`).
- Swapping storage (for example SQLite) means writing a new module in `persistence` and changing
  one line in `cli`.
- Slightly more structure than ADR-0001's "load and save the list" in `services`, but it keeps
  `services` and `domain` testable with in-memory fakes and no filesystem.
- The `SCHEMA_VERSION` constant belongs to the on-disk format and lives in `persistence`
  (the spec's stub lists it under `services`; no other layer needs it).

## Alternatives considered
- **Persistence inside `services`:** simplest, but puts `json` / `os` / `fsync` code in the layer the
  spec says must be pure and fake-testable, and breaks "services imports only domain" in spirit.
- **Persistence above `ui`/below `cli` (stacked, `ui` > `persistence`):** would let `ui` import the
  store directly; the sibling rule prevents the UI from touching storage.
- **Full hexagonal (ports and adapters packages):** rejected in ADR-0001; the single extra adapter
  package here does not change that judgement.
