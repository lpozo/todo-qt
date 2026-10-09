# Requirements — task-list

## Context
todo-qt has been bootstrapped but does nothing yet. The owner wants a desktop to-do list for
personal daily use that works as a simple day planner: tasks are time slots that run one after
another, can be reordered, and are never lost between runs. Reminders through system-tray
notifications are wanted too, but come in the next feature (`task-reminders`), built on this
one.

## Goal
A user can plan their day in a desktop window: add, edit, reschedule, reorder, complete, and
delete timed tasks, with every change saved automatically and restored on the next launch.

## Acceptance Criteria

Terms: a **task** has a title, a **start** and an **end** (date and time, end after start),
and a done flag. Its **duration** is end − start. A task is **overdue** when it isn't done and
its end is earlier than now. The list has a user-defined order. The **day start time** is
one saved time of day (default 09:00) at which the first task of a re-chained timeline begins.

### Launching
- [Must] **Given** no saved tasks exist, **When** the user runs `todo-qt`, **Then** a window
  opens showing an empty task list and a way to add a task.
- [Must] **Given** tasks were saved in a previous run, **When** the user runs `todo-qt`,
  **Then** the window shows those tasks in the same order, with the same titles, starts, ends,
  and done flags, and the saved day start time.

### Adding
- [Must] **Given** the window is open at 14:20, **When** the user starts adding a task,
  **Then** the start is pre-filled with today 15:00 and the end with today 15:30.
- [Must] **Given** the add form is open, **When** the user enters a title and confirms,
  **Then** the task appears at the bottom of the list, not done, with the chosen start and end.
- [Must] **Given** the add form is open, **When** the user confirms with an empty or
  whitespace-only title, **Then** no task is added and the user is told a title is required.
- [Must] **Given** the add form is open, **When** the user confirms with an end that is not
  after the start, **Then** no task is added and the user is told the end must be after the
  start.
- [Must] **Given** the add form is open, **When** the user confirms a start and end in the
  past, **Then** the task is added and shown as overdue.

### Editing and rescheduling
- [Must] **Given** a task "Buy milk", **When** the user edits its title to "Buy oat milk" and
  confirms, **Then** the task shows "Buy oat milk" and keeps its position, times, and done flag.
- [Must] **Given** a task, **When** the user edits its title to an empty or whitespace-only
  title, **Then** the edit is rejected and the original title is kept.
- [Must] **Given** a task, **When** the user reschedules it to a new start and end with the
  end after the start, **Then** the task shows the new times, and no other task's times or
  position change.
- [Must] **Given** a task, **When** the user reschedules it with an end that is not after the
  start, **Then** the change is rejected and the original times are kept.

### Completing
- [Must] **Given** an open task, **When** the user marks it done, **Then** it stays in its
  position, is shown struck through, and is no longer shown as overdue.
- [Must] **Given** a done task, **When** the user marks it not done, **Then** it is shown
  normally again (and as overdue if its end is in the past).

### Reordering (timeline cascade)
- [Must] **Given** tasks A 09:00–10:00, B 10:00–11:30, C 14:00–14:30 in that order, **When**
  the user drags C between A and B, **Then** the order is A, C, B with A 09:00–10:00,
  C 10:00–10:30, B 10:30–12:00.
- [Must] **Given** a list of tasks, **When** the user drags a task other than the first one to
  position *i* > 1, **Then** every task from position *i* down keeps its duration and starts at
  the end of the task above it, and the tasks above position *i* are unchanged.
- [Must] **Given** the day start is 09:00 and tasks A Fri 09:00–10:00, B Fri 10:30–11:30,
  C Fri 12:00–13:00, **When** the user drags A below B, **Then** B, the new first task, starts at
  the day start on its own date, keeping its duration, and every task below re-chains after it:
  B Fri 09:00–10:00, A Fri 10:00–11:00, C Fri 11:00–12:00.
- [Must] **Given** the day start is 09:00 and tasks A Fri 10:00–11:00, B Fri 11:00–12:00,
  C Fri 15:00–15:30, **When** the user drags C to the top, **Then** C starts at the day start on
  the date the old first task started on, keeps its duration, and the rest re-chain after it:
  C Fri 09:00–09:30, A Fri 09:30–10:30, B Fri 10:30–11:30.
- [Must] **Given** the cascade reaches a done task, **When** times are re-chained, **Then** the
  done task is re-chained like any other task (it keeps its done flag).
- [Must] **Given** a re-chained task's end moves past midnight, **When** the cascade runs,
  **Then** the task's start and end carry over into the next day correctly.

### Day start time
- [Must] **Given** the app has never been configured, **When** it starts, **Then** the day
  start time is 09:00.
- [Must] **Given** the window is open, **When** the user changes the day start time to 08:00,
  **Then** the new day start is shown, and it is still 08:00 after the app is restarted.
- [Must] **Given** the day start is 09:00 and tasks A Fri 10:00–11:00, B Fri 11:00–12:00,
  **When** the user changes the day start to 08:00, **Then** the first task moves to the new
  day start on its own date, keeping its duration, and every task below re-chains after it:
  A Fri 08:00–09:00, B Fri 09:00–10:00.
- [Must] **Given** the task list is empty, **When** the user changes the day start time,
  **Then** the new day start is saved and no tasks change.
- [Must] **Given** the day start time changes, **When** new tasks are added afterwards,
  **Then** their pre-filled start is still the next full hour (the day start doesn't affect
  it).

### Deleting and undo
- [Must] **Given** a task, **When** the user deletes it, **Then** it is removed from the list
  and no other task's times or order change.
- [Must] **Given** the user just deleted a task, **When** the user presses Ctrl+Z (Cmd+Z on
  macOS) or chooses Undo, **Then** the task reappears at its previous position with its title,
  times, and done flag.
- [Must] **Given** the user deleted task X and then task Y, **When** the user undoes, **Then**
  only Y is restored; undoing again restores nothing.
- [Must] **Given** nothing has been deleted in this session, **When** the user undoes, **Then**
  nothing changes.
- [Must] **Given** the user deleted a task and then quit, **When** the app is started again,
  **Then** undo does not restore the task (undo is per session).

### Clearing completed
- [Must] **Given** a list with done and open tasks, **When** the user chooses Clear completed,
  **Then** all done tasks are removed, and the open tasks keep their order and times.
- [Should] **Given** the user just cleared completed tasks, **When** the user undoes, **Then**
  all the cleared tasks reappear at their previous positions (Clear completed counts as one
  delete).
- [Must] **Given** no task is done, **When** the user looks at the controls, **Then** Clear
  completed is disabled.

### Overdue display
- [Must] **Given** an open task whose end is earlier than now, **When** the list is shown,
  **Then** the task is visually highlighted as overdue.
- [Should] **Given** the window stays open, **When** an open task's end passes, **Then** the
  task is highlighted as overdue within 60 seconds, without user action.

### Saving
- [Must] **Given** any change (add, edit, reschedule, reorder, complete, uncomplete, delete,
  clear completed, undo, day start time), **When** the change is made, **Then** it is saved without a Save
  action, so that killing the app right afterwards and restarting shows the change.
- [Must] **Given** the saved data can't be read (corrupt or unreadable file), **When** the app
  starts, **Then** it tells the user, starts with an empty list, and does not overwrite the
  unreadable file (it is preserved so data can be recovered).
- [Must] **Given** saving fails (for example, the disk is full or the file isn't writable),
  **When** the user makes a change, **Then** the user is told that the change wasn't saved, and
  the app keeps running with the change in the list.
- [Could] **Given** the `TODO_QT_DATA_DIR` environment variable is set, **When** the app
  starts, **Then** it reads and saves tasks in that directory instead of the default one.

### Keyboard
- [Could] **Given** the add form has a title, **When** the user presses Enter, **Then** the
  task is added as if confirmed.
- [Could] **Given** a task is selected, **When** the user presses Delete (Backspace on macOS),
  **Then** the task is deleted (and can be undone).

## Non-Goals (Won't)
- System-tray icon, notifications, and reminders — the next feature, `task-reminders`.
- Running in the background after the window is closed.
- Multiple lists, projects, categories, tags, or priorities.
- Recurring tasks.
- Undo or redo of anything other than the last delete or Clear completed; multi-level undo.
- Undo across app restarts.
- A "sort by start" action, or automatic sorting by time.
- A different day start time per date or weekday; there is one day start for every day.
- Detecting or preventing overlapping tasks (rescheduling may create overlaps; only reordering
  re-chains times).
- Search, filtering, or hiding done tasks.
- Sync, cloud storage, import, or export.
- Windows support.
- Changing time zones while the app runs; times are local wall-clock times.

## Constraints
- **Performance:** with 500 tasks, the window is usable within 2 seconds of launch, and each
  add, edit, reorder, delete, or undo updates the list and finishes saving within 200 ms on a
  typical laptop.
- **Security:** tasks are stored only on the local machine, in the user's own data directory,
  readable and writable only by that user. The app makes no network connections.
- **Data safety:** a crash or power loss during a save must never leave a partially written
  data file; the previous saved state or the new one must survive intact.
- **Compatibility:** Python ≥ 3.14 (`requires-python`). Must run on Linux and macOS. CI verifies
  Linux; macOS is checked manually until a macOS CI job exists. The Qt binding chosen in
  Phase 3 must be licensed compatibly with the project's MIT license (so LGPL-licensed, not
  GPL-only). Times are shown and entered in the system's local time zone.
- **Architecture:** follows ADR-0001 (layered): task rules — validation, the cascade, overdue —
  live in `domain` and are testable without Qt; Qt is imported only in `ui`.
- **Quality gates:** strict mypy, branch coverage ≥ 85%, and the CI jobs must pass, including
  GUI tests running headless (no display) on ubuntu-latest.
- **Deadline:** none.

## Open Questions
| Question | Owner | Deadline | Status |
|---|---|---|---|
| Add a macOS CI job (tests on macos-latest) as part of this feature or later? Assumed later; macOS checked manually in Phase 8. | @lpozo | 2026-10-16 (before `/task-define`) | open, non-blocking |
| Storage format and data directory location (JSON file vs SQLite; Qt's standard paths vs platformdirs). | Architect (Phase 3) | `/arch-plan` | deferred to Phase 3 |

## Reuse Notes
- **Prior art:** none — the package is the bootstrap skeleton: an empty `src/todo_qt/__init__.py`
  and `src/todo_qt/cli.py`, whose `main() -> int` is the entry point (`todo-qt =
  "todo_qt.cli:main"`) and, per ADR-0001, the composition root that will create the Qt
  application and wire the layers.
- **Architecture:** ADR-0001 sets the layers `ui` → `services` → `domain`, with Qt allowed only
  in `ui`. It doesn't say where persistence lives; Phase 3 must decide (an ADR if it changes the
  layers). `[tool.importlinter]` has no contracts yet — this feature's walking skeleton adds the
  layers contract and the "no Qt below `ui`" contract.
- **Dependencies:** no Qt binding or pytest-qt yet; adding them updates `uv.lock` (CI uses
  `uv sync --locked`) and they must pass `pip-audit`. Researched options (to be decided in
  Phase 3): PySide6 / PySide6-Essentials 6.12 (LGPL-3.0 or GPL, abi3 wheels usable on 3.14,
  ships type hints) and PyQt6 6.11 (GPL-3.0-only, which conflicts with MIT). pytest-qt 4.5
  (MIT) supports both; its 3.14 support should be confirmed early with a spike.
- **Strict typing:** mypy runs with `strict` and `disallow_any_unimported`; Qt subclasses,
  signals, and slots may need care — worth an early spike.
- **Headless GUI tests:** set `QT_QPA_PLATFORM=offscreen` (e.g. in `tests/conftest.py`); CI's
  test job may need Qt runtime libraries via apt (`libegl1`, `libgl1`, `libxkbcommon0`,
  `libdbus-1-3`, `libfontconfig1`, `libglib2.0-0`). Avoid modal dialogs that block in tests.
  `-n auto` runs each xdist worker in its own process, which suits a per-process
  `QApplication`.
- **Testability:** inject the data directory and the clock (for "now", the pre-filled start,
  and overdue) instead of reading them globally, so tests use `tmp_path` and fixed times.
  Keep the UI thin to protect the 85% coverage gate.
- **Conventions:** fully typed code, one-line docstrings, ruff (line length 100), Conventional
  Commits; feature tests go in `tests/<feature>/` with an `__init__.py`. No logging, error,
  or config conventions exist yet.
