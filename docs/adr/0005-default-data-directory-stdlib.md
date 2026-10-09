# 0005. Default data directory computed with the standard library
Status: Accepted
Date: 2026-10-09

## Context
`cli.resolve_data_dir(environ, default_dir)` needs a platform default for the data directory on
Linux and macOS. Options: Qt's `QStandardPaths` (only callable where Qt is allowed, and its result
depends on `QCoreApplication` organisation / application names being set first), `platformdirs`
(new dependency), or a few lines of stdlib logic. `main` must stay testable without Qt (`run_ui` is
injected) and without touching the real home directory in tests.

## Decision
Implement a pure function `default_data_dir(environ: Mapping[str, str], home: Path, platform: str)
-> Path` in `todo_qt.persistence.locations`:

- Linux (and other non-macOS POSIX): `$XDG_DATA_HOME/todo-qt` when `XDG_DATA_HOME` is set, non-empty,
  and absolute; otherwise `<home>/.local/share/todo-qt`.
- macOS (`platform == "darwin"`): `<home>/Library/Application Support/todo-qt`.

These are the same locations `QStandardPaths.AppDataLocation` yields for an application named
`todo-qt` with no organisation name, so a later Qt-based feature (such as `task-reminders`) can
read the same directory. `cli.main` calls it with `os.environ`, `Path.home()`, and `sys.platform`, then
passes the result as `default_dir` to `resolve_data_dir`. The `TODO_QT_DATA_DIR` override is applied
by `resolve_data_dir` and wins over everything.

## Consequences
- No new dependency; no Qt in `cli` or `persistence`; fully unit-testable with plain dicts.
- Windows is a non-goal; `default_data_dir` treats it as POSIX and would need a new branch (and
  ADR note) when Windows support is added.
- If the Qt names ever change, the directory must be kept stable by hand (or migrated).

## Alternatives considered
- **`QStandardPaths`:** forces `cli` to import Qt (violating "Qt only in `ui`") or `ui` to be loaded
  just to learn a path, and requires `QCoreApplication` names set first.
- **`platformdirs`:** a third-party dependency (to audit and keep locked) for two path rules.
