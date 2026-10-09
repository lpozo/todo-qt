"""JSON-file implementation of the plan store port."""

import os
from datetime import datetime
from pathlib import Path
from typing import TextIO

from todo_qt.persistence import codec
from todo_qt.services import Clock, PlanSnapshot

FILE_NAME = "tasks.json"


class JsonPlanStore:
    """Store the plan as a JSON file in a data directory."""

    def __init__(self, directory: Path, now: Clock | None = None) -> None:
        """Remember the data directory and the clock used to name .corrupt files."""
        self._path = directory / FILE_NAME
        self._now = now or datetime.now

    def load(self) -> PlanSnapshot | None:
        """Return the saved plan, or None if nothing was ever saved."""
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return codec.decode(text)

    def save(self, snapshot: PlanSnapshot) -> None:
        """Persist the snapshot through a temp file replaced over the data file."""
        _make_private_dirs(self._path.parent)
        temp = self._path.with_name(f"{FILE_NAME}.{os.getpid()}.tmp")
        with _create_private_file(temp) as file:
            file.write(codec.encode(snapshot))
        os.replace(temp, self._path)


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
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")
