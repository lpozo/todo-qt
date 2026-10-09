"""JSON-file implementation of the plan store port."""

import contextlib
import os
from datetime import datetime
from pathlib import Path
from typing import TextIO

from todo_qt.persistence import codec
from todo_qt.services import Clock, PlanSnapshot, StoreCorruptError, StoreWriteError

FILE_NAME = "tasks.json"


class JsonPlanStore:
    """Store the plan as a JSON file in a data directory."""

    def __init__(self, directory: Path, now: Clock | None = None) -> None:
        """Remember the data directory and the clock used to name .corrupt files."""
        self._path = directory / FILE_NAME
        self._now = now or datetime.now
        self._corrupt = False

    def load(self) -> PlanSnapshot | None:
        """Return the saved plan, or None if nothing was ever saved."""
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._corrupt = False
            return None
        except (OSError, UnicodeDecodeError) as error:
            self._corrupt = True
            raise StoreCorruptError(self._path, f"cannot read: {error}") from error
        try:
            plan = codec.decode(text)
        except codec.CodecError as error:
            self._corrupt = True
            raise StoreCorruptError(self._path, str(error)) from error
        self._corrupt = False
        return plan

    def save(self, snapshot: PlanSnapshot) -> None:
        """Atomically persist the snapshot, raising StoreWriteError on any failure."""
        temp = self._path.with_name(f"{FILE_NAME}.{os.getpid()}.tmp")
        try:
            _make_private_dirs(self._path.parent)
            if self._corrupt:
                self._preserve_corrupt_file()
            _write_atomically(temp, self._path, codec.encode(snapshot))
            self._corrupt = False
        except OSError as error:
            raise StoreWriteError(self._path, str(error)) from error

    def _preserve_corrupt_file(self) -> None:
        """Rename the unreadable file aside to tasks.<timestamp>.corrupt."""
        stamp = self._now().strftime("%Y%m%d-%H%M%S")
        aside = self._path.with_name(f"tasks.{stamp}.corrupt")
        counter = 0
        while aside.exists() or aside.is_symlink():
            counter += 1
            aside = self._path.with_name(f"tasks.{stamp}.{counter}.corrupt")
        # FileNotFoundError: the file vanished since load, so there is nothing to preserve.
        with contextlib.suppress(FileNotFoundError):
            os.rename(self._path, aside)


def _write_atomically(temp: Path, target: Path, text: str) -> None:
    """Write `text` to `temp`, fsync it, and replace `target`; clean up on failure."""
    try:
        with _create_private_file(temp) as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            temp.unlink()
        raise
    _fsync_directory(target.parent)


def _fsync_directory(directory: Path) -> None:
    """Best-effort fsync of `directory` so the rename is durable (unsupported on some OSes)."""
    # Errors are deliberately ignored: the replace already succeeded (ADR-0004).
    with contextlib.suppress(OSError):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _make_private_dirs(directory: Path) -> None:
    """Create `directory` and missing parents, setting 0o700 only on those created."""
    missing: list[Path] = []
    current = directory
    while not current.exists() and current != current.parent:
        missing.append(current)
        current = current.parent
    for path in reversed(missing):
        path.mkdir()
        os.chmod(path, 0o700)


def _create_private_file(path: Path) -> TextIO:
    """Exclusively create `path` with mode 0o600, replacing a stale leftover once."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        path.unlink()
        fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        return os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
