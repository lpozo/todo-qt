# Architecture — task-list

Style: layered, per ADR-0001, amended by ADR-0003 (a `persistence` layer beside `ui`).
Inputs: `spec.md` (the contract) and `requirements.md` (constraints).

## Module Decomposition

Layers, top to bottom (siblings on one line are independent of each other):

```
cli                      composition root: wires everything, starts the app
ui | persistence         Qt widgets            |  file-backed PlanStore adapter
services                 PlanService, PlanStore port, store errors
domain                   Plan, Task, TimeSlot, the cascade, overdue (stdlib only)
```

| Module | Responsibility | Imports (project / third-party / stdlib I/O) |
|---|---|---|
| `todo_qt/domain/errors.py` | `DomainError` and all subclasses | stdlib only |
| `todo_qt/domain/task.py` | `TaskId`, `normalize_title`, `TimeSlot`, `Task`, `RemovedEntry`, `RemovedTasks` | `domain.errors` |
| `todo_qt/domain/plan.py` | `Plan` (add, edit, reschedule, done, delete, clear, restore, move, set_day_start), `DEFAULT_DAY_START`, private chaining helper | `domain.errors`, `domain.task` |
| `todo_qt/domain/schedule.py` | `default_slot`, `is_overdue`, `DEFAULT_SLOT_DURATION` | `domain.errors`, `domain.task` |
| `todo_qt/domain/__init__.py` | Re-exports the whole public domain API (the spec says `todo_qt.domain`) | `domain.*` |
| `todo_qt/services/errors.py` | `StoreError`, `StoreCorruptError`, `StoreWriteError` | stdlib (`pathlib`) |
| `todo_qt/services/ports.py` | `PlanStore` Protocol, `PlanSnapshot`, `Clock`, `IdFactory` | `domain` |
| `todo_qt/services/plan_service.py` | `ChangeResult`, `PlanService` (auto-save, one-slot undo, queries) | `domain`, `services.errors`, `services.ports` |
| `todo_qt/services/__init__.py` | Re-exports the public services API | `services.*` |
| `todo_qt/persistence/codec.py` | `SCHEMA_VERSION`, `encode(Plan) -> dict`, `decode(obj) -> Plan` (strict validation) | `domain` (pure dict mapping, no I/O) |
| `todo_qt/persistence/json_store.py` | `JsonPlanStore` (implements `PlanStore`): atomic write, permissions, corrupt-file preservation | `domain`, `services`, `persistence.codec`, `json`, `os` |
| `todo_qt/persistence/locations.py` | `default_data_dir(environ, home, platform)` (ADR-0005) | stdlib `pathlib` |
| `todo_qt/ui/messages.py` | **Qt-free.** Exact user-visible strings; maps `DomainError` / `Store*Error` to messages | `domain`, `services` |
| `todo_qt/ui/controller.py` | **Qt-free.** `UiController`: runs service commands, converts raised `DomainError` to a notifier message, reports `save_error`, calls `on_change` | `domain`, `services`, `ui.messages` |
| `todo_qt/ui/convert.py` | `QDateTime`/`QTime` <-> naive minute-precision `datetime`/`time` | `PySide6.QtCore` |
| `todo_qt/ui/task_model.py` | `TaskListModel(QAbstractListModel)`: rows from `service.plan`, roles for done/overdue/strike, drag and drop (`dropMimeData` -> `controller.move`) | `PySide6`, `domain`, `services`, `ui.controller` |
| `todo_qt/ui/task_form.py` | Inline (non-modal) form widget for add and for edit title/times; title, start, end fields, Enter confirms, inline error label | `PySide6`, `ui.convert`, `ui.controller` |
| `todo_qt/ui/main_window.py` | `MainWindow`: list view, form, Clear completed, Undo action (Ctrl+Z / Cmd+Z), day-start `QTimeEdit`, message label, overdue `QTimer`, Delete key | `PySide6`, `ui.*`, `services` |
| `todo_qt/ui/app.py` | `run_app(service) -> int`: creates/reuses `QApplication`, shows the window, runs the loop | `PySide6`, `ui.main_window` |
| `todo_qt/ui/__init__.py` | Exports `run_app` only | `ui.app` |
| `todo_qt/cli.py` | `DATA_DIR_ENV_VAR`, `resolve_data_dir`, `main`, `system_clock`, `new_task_id`; lazy-imports `todo_qt.ui` for the default `run_ui` | all layers, `os`, `sys`, `uuid` |

Notes on the table: the `codec` module does dict <-> `Plan` mapping only (no I/O, so it is unit-tested
without files); `json_store` owns `json`, `os`, and temp-file handling.

### Where each design question lands

- **`PlanStore` implementation:** `todo_qt.persistence.json_store.JsonPlanStore` (ADR-0003, ADR-0004).
  The port itself and the errors live in `todo_qt.services`.
- **`PlanService`:** `todo_qt.services.plan_service` (re-exported from `todo_qt.services`).
- **Clock and id injection:** `PlanService.__init__(store, clock, new_id)`. `cli` supplies
  `system_clock = lambda: datetime.now()` (naive, local) and `new_task_id = lambda: TaskId(uuid4().hex)`.
  Tests pass lambdas/counters. Nothing below `cli` reads the wall clock, the environment, or `uuid`.
  (`JsonPlanStore` takes an optional `now` callable only to name `.corrupt` files.)
- **Data directory:** `cli.main` computes `default_data_dir(os.environ, Path.home(), sys.platform)`
  and `resolve_data_dir(environ, that)`; no Qt, no `platformdirs` (ADR-0005). It returns `1` when the
  resolved path exists and is not a directory; it never creates the directory (the store does on first save).
- **Service errors in the UI:** `UiController` calls the service; `DomainError`s propagate from the
  service unchanged and are caught only there, then mapped by `ui.messages.message_for(error)`:
  `EmptyTitleError` -> `A title is required.`, `EndNotAfterStartError` -> `The end must be after the start.`
  (check the subclass before `InvalidTimeSlotError`); any other `DomainError` -> its `str()`.
  `ChangeResult.save_error` -> `save_failure_message(error)`; `service.startup_error` ->
  `startup_message(error)`, shown once by `MainWindow.__init__`. Messages go to an injectable
  `Notifier = Callable[[str], None]`; the default shows them in the window's message label, so
  nothing ever blocks.
- **Add-form validation order:** `UiController.add_task(title, start, end)` calls
  `normalize_title` first, then builds the `TimeSlot`, then `service.add_task`, so the title message
  wins over the slot message (spec). Same flow for reschedule (slot only).
- **Overdue refresh:** `MainWindow` owns a `QTimer` with `OVERDUE_REFRESH_MS = 15_000` (spec: at most
  30 s), connected to `refresh_overdue()`, which re-reads `service.overdue_ids()` and emits
  `dataChanged` over the rows only if the overdue set changed. Every list refresh also recomputes it.
  Tests call `window.overdue_timer.timeout.emit()` and assert `interval() <= 30_000`.
- **Drag to reorder:** `QListView` in `InternalMove` mode with `Qt.MoveAction` only.
  `TaskListModel.dropMimeData(data, action, row, col, parent)` converts the drop position (an insertion
  point *before* removal, `-1` meaning "append") into the spec's **final index**
  (`row - 1` when `row > old_index`, `row` when `row <= old_index`, `len - 1` for append), calls
  `controller.move(task_id, final)`, resets the model, and returns `True`. `removeRows` is not
  implemented (returns `False`), so Qt never removes the source row itself; the list always re-renders
  from `service.plan`. The conversion is a pure function (`final_index(old, drop_row, size)`) in
  `ui/task_model.py`, unit-tested without events.
- **Highlight/strike rendering:** model roles (`FontRole` strike-out for done, `BackgroundRole` for
  overdue, `CheckStateRole` for the done checkbox) plus a custom `OverdueRole` and `DoneRole` so tests
  assert state without comparing colors.
- **Day start:** `QTimeEdit` wired to `editingFinished` (not `timeChanged`, to avoid re-chaining on every
  keystroke) -> `controller.set_day_start`. The control is re-populated from `plan.day_start` on each refresh
  with its signals blocked.
- **Unsolicited behavior kept out of the UI:** no task rule, no sorting, no time arithmetic in
  `ui`. `convert.py` only truncates seconds on the way in.

## Directory Tree

New and changed files only.

```
todo-qt/
│
├── src/
│   │
│   └── todo_qt/
│       ├── cli.py                  ← changed: composition root
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── errors.py
│       │   ├── plan.py
│       │   ├── schedule.py
│       │   └── task.py
│       │
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── codec.py
│       │   ├── json_store.py
│       │   └── locations.py
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── errors.py
│       │   ├── plan_service.py
│       │   └── ports.py
│       │
│       └── ui/
│           ├── __init__.py
│           ├── app.py
│           ├── controller.py
│           ├── convert.py
│           ├── main_window.py
│           ├── messages.py
│           ├── task_form.py
│           └── task_model.py
│
├── tests/
│   │
│   ├── conftest.py                 ← new: QT_QPA_PLATFORM=offscreen
│   ├── test_cli.py                 ← changed: see "Existing tests" below
│   │
│   └── task_list/
│       ├── __init__.py
│       ├── fakes.py                ← FakeStore, RecordingStore, fixed clock, id counter
│       ├── test_cli_main.py
│       ├── test_domain_plan.py
│       ├── test_domain_plan_move.py
│       ├── test_domain_schedule.py
│       ├── test_domain_task.py
│       ├── test_persistence_json_store.py
│       ├── test_persistence_locations.py
│       ├── test_service_autosave.py
│       ├── test_service_commands.py
│       ├── test_service_queries.py
│       ├── test_service_startup.py
│       ├── test_service_undo.py
│       ├── test_ui_controller.py
│       ├── test_ui_messages.py
│       ├── test_ui_model.py
│       └── test_ui_window.py
│
├── docs/adr/                       ← 0002 .. 0006 (new)
└── pyproject.toml, uv.lock, .github/workflows/ci.yml   ← changed by the walking skeleton (below)
```

## Spec-to-module mapping

Test files are under `tests/task_list/`. Example numbers refer to the spec tables.

| Spec section (examples) | Module | Test file |
|---|---|---|
| Domain errors | `todo_qt/domain/errors.py` | covered via the sections below |
| `normalize_title` (1-3) | `todo_qt/domain/task.py` | `test_domain_task.py` |
| `TimeSlot` (1-6) | `todo_qt/domain/task.py` | `test_domain_task.py` |
| `Task` (1-2), `RemovedTasks` invariant | `todo_qt/domain/task.py` | `test_domain_task.py` |
| `Plan.add` (1-5), `edit_title` (1-3), `reschedule` (1-3), `set_done` (1-3), `delete` (1-2), `clear_completed` (1-2), `restore` (1-6) | `todo_qt/domain/plan.py` | `test_domain_plan.py` |
| `Plan.move` (1-12, 9b, 9c) | `todo_qt/domain/plan.py` | `test_domain_plan_move.py` |
| `Plan.set_day_start` (1-7), default day start (3) | `todo_qt/domain/plan.py` | `test_domain_plan_move.py` |
| `default_slot` (1-6), `is_overdue` (1-6) | `todo_qt/domain/schedule.py` | `test_domain_schedule.py` |
| `PlanStore` (store_* 1-9) | `todo_qt/persistence/json_store.py` + `codec.py` | `test_persistence_json_store.py` |
| Default data dir (not in spec; ADR-0005) | `todo_qt/persistence/locations.py` | `test_persistence_locations.py` |
| `PlanService` construction (1-5) | `todo_qt/services/plan_service.py` | `test_service_startup.py` |
| `add_task` (1-4), `edit_title`/`reschedule`/`set_done` (1-6), `move_task` and `set_day_start` (1-5) | `todo_qt/services/plan_service.py` | `test_service_commands.py` |
| `delete_task`/`clear_completed`/`undo` (1-12) | `todo_qt/services/plan_service.py` | `test_service_undo.py` |
| Auto-save and save failures (1-6) | `todo_qt/services/plan_service.py` (+ `JsonPlanStore` for 2 and 6) | `test_service_autosave.py` |
| Queries (1-4) | `todo_qt/services/plan_service.py` | `test_service_queries.py` |
| `resolve_data_dir` (1-3), `main` (4 of the resolve table, and 1-6) | `todo_qt/cli.py` | `test_cli_main.py` |
| UI examples 1, 2, 3, 4, 7, 16, 18, 19, 20 | `ui/main_window.py`, `task_form.py`, `task_model.py` | `test_ui_window.py` |
| UI examples 5, 6, 8, 9 (messages and rejection) | `ui/controller.py` + `ui/messages.py` (Qt-free logic); form/window wiring | `test_ui_controller.py` (logic), `test_ui_window.py` (one wiring check each) |
| UI examples 10, 11 (strike, overdue roles) | `ui/task_model.py` | `test_ui_model.py` |
| UI example 12 (drag), final-index conversion | `ui/task_model.py` (`dropMimeData`, `final_index`) | `test_ui_model.py` |
| UI example 13 (day start) | `ui/main_window.py` | `test_ui_window.py` |
| UI examples 14, 15, 17 (Ctrl+Z, undo none, clear + undo) | `ui/main_window.py` | `test_ui_window.py` |
| UI examples 21, 22 [Could] (Enter, Delete key) | `ui/task_form.py`, `ui/main_window.py` | `test_ui_window.py` |
| UI message strings | `ui/messages.py` | `test_ui_messages.py` |

UI tests use `qtbot` with `FakeStore` and a mutable fixed clock; shortcuts are tested by
`qtbot.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)` (with the `Undo`
`QAction` shortcut context `WindowShortcut`).

## Key Decisions
- ADR-0002: Qt binding — `pyside6-essentials>=6.12,<7` (LGPL, typed; PyQt6 is GPL-only).
- ADR-0003: Persistence layer — a `persistence` layer beside `ui`, implementing the `services` port; amends ADR-0001.
- ADR-0004: Storage — one `tasks.json`, temp file + fsync + `os.replace`, `0600`/`0700`, corrupt files renamed aside to `tasks.<timestamp>.corrupt` before the first save.
- ADR-0005: Default data dir — stdlib XDG / `~/Library/Application Support`, matching `QStandardPaths`; no `platformdirs`.
- ADR-0006: GUI tests — `pytest-qt`, `QT_QPA_PLATFORM=offscreen` in `tests/conftest.py`, apt libs on CI.

## Library Choices

| Need | Choice | Rationale |
|---|---|---|
| Qt binding | `pyside6-essentials>=6.12,<7` (**new runtime dep**) | Only LGPL option compatible with MIT; ships type hints; spike passed on Python 3.14 (ADR-0002) |
| GUI tests | `pytest-qt>=4.5` (**new dev dep**) | Standard; supports PySide6; spike passed (ADR-0006) |
| Storage | stdlib `json`, `os` | Tiny document, whole-file atomic rewrite (ADR-0004) |
| Paths | stdlib `pathlib`, `os.environ`, `sys.platform` | Avoids `platformdirs` (ADR-0005) |
| Ids | stdlib `uuid.uuid4().hex` in `cli` | Unique, no dependency |
| Time | stdlib `datetime` (naive local) | Spec's time model; no `zoneinfo` or `tzdata` |
| Other test tools | existing `pytest`, `pytest-xdist`, `pytest-cov`, `hypothesis` | Hypothesis suits the `move` invariants (example 12) and codec roundtrips |

No other dependency is added.

## Diagrams

```mermaid
flowchart TB
    subgraph cli_["cli (composition root)"]
        main["main() / resolve_data_dir"]
    end
    subgraph ui_["ui (PySide6)"]
        win["MainWindow + TaskListModel + TaskForm"]
        ctl["UiController + messages (Qt-free)"]
    end
    subgraph per_["persistence"]
        store["JsonPlanStore + codec + locations"]
    end
    subgraph svc_["services"]
        svc["PlanService"]
        port["PlanStore (Protocol) + Store*Error"]
    end
    subgraph dom_["domain"]
        dom["Plan, Task, TimeSlot, default_slot, is_overdue"]
    end
    main -->|builds and injects| store
    main -->|builds| svc
    main -->|run_ui(service)| win
    win --> ctl
    ctl --> svc
    svc --> port
    svc --> dom
    store -.implements.-> port
    store --> dom
    disk[("tasks.json")]
    store --> disk
```

## Architecture Enforcement

import-linter contracts. The walking-skeleton task copies them into `pyproject.toml` together with
the modules they constrain (`root_packages` stays `["todo_qt"]`, `include_external_packages = true`).
Verified in a throwaway project (import-linter, `|` sibling layers are independent by default; stdlib
names such as `json` and `os` are accepted in `forbidden_modules`).

```toml
[[tool.importlinter.contracts]]
name = "Layers: cli, then ui and persistence, then services, then domain"
type = "layers"
layers = [
  "todo_qt.cli",
  "todo_qt.ui | todo_qt.persistence",
  "todo_qt.services",
  "todo_qt.domain",
]

[[tool.importlinter.contracts]]
name = "Qt is imported only in ui"
type = "forbidden"
source_modules = [
  "todo_qt.domain",
  "todo_qt.services",
  "todo_qt.persistence",
  "todo_qt.cli",
]
forbidden_modules = ["PySide6", "shiboken6", "PyQt6", "PyQt5", "PySide2"]

[[tool.importlinter.contracts]]
name = "Domain does no I/O"
type = "forbidden"
source_modules = ["todo_qt.domain"]
forbidden_modules = [
  "json", "sqlite3", "os", "pathlib", "shutil", "tempfile", "uuid", "socket", "urllib", "http",
]

[[tool.importlinter.contracts]]
name = "Services do no file or network I/O"
type = "forbidden"
source_modules = ["todo_qt.services"]
forbidden_modules = ["json", "sqlite3", "os", "shutil", "tempfile", "uuid", "socket", "urllib", "http"]

[[tool.importlinter.contracts]]
name = "UI controller and messages stay Qt-free"
type = "forbidden"
source_modules = ["todo_qt.ui.controller", "todo_qt.ui.messages"]
forbidden_modules = ["PySide6", "shiboken6", "PyQt6", "PyQt5", "PySide2"]

[[tool.importlinter.contracts]]
name = "No network anywhere"
type = "forbidden"
source_modules = ["todo_qt"]
forbidden_modules = [
  "socket", "ssl", "urllib", "http", "ftplib", "smtplib", "requests", "httpx", "aiohttp",
  "PySide6.QtNetwork",
]
```

Rule of thumb for `services`: `pathlib` is allowed there (only to type `StoreError.path`), `os` is not.

## Changes the walking-skeleton task makes outside `src/`

(Listed here so Phase 4/5 plans them; this phase does not edit them.)
- `pyproject.toml`: add `pyside6-essentials>=6.12,<7` to `dependencies`; add `pytest-qt>=4.5` to the
  `dev` group; add `qt_api = "pyside6"` to `[tool.pytest.ini_options]`; add the contracts above.
  Run `uv lock` (CI uses `uv sync --locked`).
- `.github/workflows/ci.yml` `test` job: a step before pytest,
  `sudo apt-get update && sudo apt-get install -y --no-install-recommends libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libglib2.0-0t64`.
  The `types` job needs no system libs (mypy reads the wheels' stubs).
- `tests/conftest.py`: `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before any Qt import.
- `tests/test_cli.py` currently asserts `main() == 0` for the stub. With the real `main`, a no-argument
  call would start the event loop on the user's real data directory, so replace it with
  `main([], environ={...}, run_ui=fake)` tests (`tests/task_list/test_cli_main.py`). `src/todo_qt/cli.py` must keep
  `main()` callable with no arguments for the console script, but no test may call it that way.

## Testing and coverage strategy

- Domain, services, persistence, cli: no Qt import; run in milliseconds; carry most of the 85% gate.
- `ui/controller.py` and `ui/messages.py` are Qt-free so error mapping and "which service call" are covered by
  plain unit tests; widgets are thin and driven by a few `qtbot` tests (22 UI examples).
- `# pragma: no cover` only on the `if __name__ == "__main__"` guard in `cli.py`. `run_app` is smoke-tested by
  scheduling `QTimer.singleShot(0, app.quit)` before calling it.
- xdist: each worker is a separate process with its own `QApplication` (pytest-qt `qapp`); no shared files.
- Spike results (2026-10-09, `/tmp/spike-qt`, throwaway, uv): `pyside6-essentials` 6.12.0 and `shiboken6` 6.12.0
  installed on Python 3.14.6; `pytest-qt` 4.5.0, `pytest` 9.1.1, `pytest-xdist` 3.8.0, `mypy` 2.4.0.
  `mypy` with `strict = true`, `disallow_any_unimported = true`, `warn_unreachable = true` accepted a
  `QMainWindow` + `QAbstractListModel` (data/flags/dropMimeData overrides) + `QTimer` + `QAction` + `Signal` module with no
  ignores (index parameters need `QModelIndex | QPersistentModelIndex`). A `qtbot` test with
  `QT_QPA_PLATFORM=offscreen` passed under `pytest -n 2`. No system library was missing on the dev VM
  (`ldd` clean for `libQt6Core/Gui/Widgets` and `libqoffscreen.so`); the apt list above is the conservative
  set for a bare ubuntu-latest runner and is not verified on CI yet. Real drag-and-drop through a `QListView` was
  not exercised in the spike; the `dropMimeData` design relies on Qt's documented behavior (a model that does not
  implement `removeRows` is not asked to delete the source row) and should be confirmed in the first UI task.
