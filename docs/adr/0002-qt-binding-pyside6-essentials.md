# 0002. Qt binding: PySide6-Essentials
Status: Accepted
Date: 2026-10-09

## Context
The `task-list` feature adds the first GUI. todo-qt is MIT-licensed, so the Qt binding must be
LGPL-compatible (requirements, Constraints). The binding must install on Python >= 3.14, ship
type hints (CI runs `mypy` with `strict` and `disallow_any_unimported`), and be supported by
`pytest-qt`. This feature needs only widgets, model/view, timers, and basic GUI classes.

## Decision
Use **`pyside6-essentials`** (the Qt for Python binding without the add-on modules), pinned as
`pyside6-essentials>=6.12,<7` in `[project] dependencies`. It is the only new runtime dependency
of the feature. Qt is imported as `PySide6.*` and only from `todo_qt.ui`.

Spike (2026-10-09, Linux x86-64, Python 3.14.6): `uv add pyside6-essentials` installed 6.12.0 (plus
`shiboken6` 6.12.0) from abi3 wheels; a `QMainWindow` / `QAbstractListModel` / `QTimer` /
`QAction` / `Signal` snippet passed `mypy` 2.4.0 with `strict = true` and
`disallow_any_unimported = true`, with no `type: ignore`.

## Consequences
- LGPL-3.0 (dynamic linking via wheels) is compatible with distributing an MIT project; the
  README should mention it when packaging.
- Adds roughly 100 MB of wheels to `uv.lock`; `pip-audit` in CI now also audits `pyside6-essentials`
  and `shiboken6`.
- The `task-reminders` feature (system tray: `QSystemTrayIcon`, in `QtWidgets`) is covered by
  Essentials; if a later feature needs an add-on module (Charts, WebEngine), switching to the
  `pyside6` meta-package is a one-line dependency change, with no code change.
- Switching to another binding later would touch only `todo_qt.ui` (ADR-0001), plus the
  forbidden-imports contract.
- Strict-typing notes from the spike: override signatures use
  `QModelIndex | QPersistentModelIndex` for index parameters; `data()` returns `Any`.

## Alternatives considered
- **PyQt6:** GPL-3.0-only (or a paid commercial licence); conflicts with the MIT / LGPL constraint.
- **`pyside6` meta-package:** same licence and API, but pulls in the add-on wheels
  (WebEngine, 3D, Charts, ...) that nothing here uses; larger CI downloads and a larger audit surface.
- **PySide2 / PyQt5 (Qt 5):** end of life, no Python 3.14 wheels.
