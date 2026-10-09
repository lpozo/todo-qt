# 0004. Storage: one JSON file, atomic replace, user-only permissions
Status: Accepted
Date: 2026-10-09

## Context
The spec fixes a logical schema (`schema_version`, `day_start`, `tasks[]`), atomic saves, user-only
permissions (`0o700` directory, `0o600` file on POSIX), refusal to destroy unreadable data, and
< 200 ms add / edit / move / delete / undo with 500 tasks (save included). It leaves the byte
format, file names, and the preservation mechanism to Phase 3. The whole plan is one small
document (500 tasks is about 60 KB), always saved and loaded as a whole snapshot.

## Decision
**Format.** A single UTF-8 JSON file, `tasks.json`, written with the stdlib `json` module:

```json
{"schema_version": 1, "day_start": "09:00",
 "tasks": [{"id": "…", "title": "…", "start": "2026-10-09T15:00",
            "end": "2026-10-09T15:30", "done": false}]}
```

Times use `%H:%M` and `%Y-%m-%dT%H:%M` (strict `datetime.strptime`; no zone, minute precision).
`json.dumps(..., ensure_ascii=False, indent=2)` so users can read and recover the file. The loader
ignores unknown extra fields at version 1, rejects `schema_version != 1` (also booleans, which are
`int` in Python), and rebuilds the `Plan` through the domain constructors; every `OSError` other than
"file not found", `UnicodeDecodeError`, `json.JSONDecodeError`, `KeyError`, `TypeError`, `ValueError`,
and `DomainError` becomes `StoreCorruptError(path, reason)`. A missing `tasks.json` returns `None`.
`load()` never writes, renames, or deletes.

**Atomic save.** `JsonPlanStore.save`: create the data directory if missing (`mkdir(mode=0o700,
parents=True)`); create a temp file in the same directory (`tasks.json.<pid>.tmp`) with
`os.open(..., O_WRONLY | O_CREAT | O_EXCL, 0o600)`; write; `flush`; `os.fsync(fd)`;
`os.replace(tmp, tasks.json)`; `fsync` the directory (best effort). On any failure the temp file is
removed and `StoreWriteError(path, reason)` is raised; `tasks.json` is never opened for writing
directly, so the previous snapshot survives.

**Permissions.** The file is born `0o600` (via `os.open`, then an `os.chmod(0o600)` guard). A data
directory the store creates is `0o700` (explicit `chmod` after `mkdir`, because `mkdir` honours the
umask). A directory that already exists is not modified (the user may point `TODO_QT_DATA_DIR` at a
directory the app does not own); the file's `0o600` still protects the content.

**Unreadable data is preserved.** The store remembers when its own `load()` raised
`StoreCorruptError`. The first `save()` after that, before writing, renames `tasks.json` to
`tasks.<YYYYMMDD-HHMMSS>.corrupt` in the same directory (a numeric suffix is appended on a name
clash) with `os.rename`, then performs the normal atomic write; the flag is cleared only after
success. If the rename fails, `save()` raises `StoreWriteError` and writes nothing. The name
timestamp comes from an injectable `now` callable (default: the system clock).
A crash between the rename and the replace leaves no `tasks.json` and an intact `.corrupt` file,
which the next launch reads as "nothing saved".

## Consequences
- Whole-file rewrite on each change is O(n) and well within 200 ms for 500 tasks (fsync dominates,
  typically a few ms on SSDs); no incremental writes or journaling to maintain.
- Human-readable and diff-able data; recovery from a `.corrupt` copy is a text-editor job.
- No migrations tooling is needed now; `schema_version` gates future formats (an unknown version
  is treated as unreadable and preserved, never overwritten silently).
- Multiple app instances are unsupported (spec); no file locking.
- macOS: `os.fsync` does not force a full disk flush (`F_FULLFSYNC`); accepted for a personal
  day planner. `os.replace` atomicity holds on APFS.
- New stdlib-only code in `todo_qt.persistence`; no new dependency.

## Alternatives considered
- **stdlib `sqlite3`:** transactional and atomic for free, but the data is one tiny document
  that is always rewritten whole; it adds a binary, non-human-readable format, `-wal`/`-journal`
  side files with their own permissions, and makes "preserve an unreadable database" and
  "reject partial snapshots" harder to do and to test than with one file.
- **One file per task or an append-only log:** more files to keep atomic and consistent; no benefit at
  this size.
- **Writing in place or `shutil.copy` + truncate:** not crash-safe; rejected by the data-safety constraint.
