# 0001. Architecture style: layered
Status: Accepted
Date: 2026-10-09

## Context
todo-qt is a desktop application: a to-do list with a Qt graphical user interface, launched
with the `todo-qt` command. Its I/O is the GUI (user input and rendering) and local persistence
of the to-do items (files or an embedded database). The core logic — creating, completing,
editing, ordering, and filtering tasks — should be testable without starting a Qt event loop.

## Decision
The `todo_qt` package is split into three layers, each importing only the layers below it:

- `todo_qt.ui` — Qt widgets, windows, and view models. The only layer that imports the Qt
  binding.
- `todo_qt.services` — application use cases (add a task, mark it done, load and save the list)
  that coordinate the domain and persistence.
- `todo_qt.domain` — framework-free models and rules for to-do items. It imports nothing from
  the other layers and no Qt.

`todo_qt.cli` is the composition root: it wires the layers together and starts the
application. It sits above all three layers.

## Consequences
Enforced by import-linter contracts added with each feature's walking skeleton: a layers
contract for `ui` → `services` → `domain`, and a forbidden contract keeping the Qt binding out
of `services` and `domain`. The domain and services can be unit-tested headlessly, and the
GUI toolkit could be swapped by rewriting only `ui`.
A feature that needs a different structure gets its own ADR that says why.

## Alternatives considered
- **Simple modules:** less ceremony, but nothing would stop Qt types from spreading into the
  task logic, making it hard to test without a display.
- **Hexagonal:** a stricter ports-and-adapters split pays off with several I/O channels and
  rich business rules. A single-user to-do app with one UI and one store doesn't need the
  extra indirection yet; it can be adopted later through a new ADR.
