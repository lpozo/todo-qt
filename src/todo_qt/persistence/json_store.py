"""JSON-file implementation of the plan store port."""

from datetime import datetime
from pathlib import Path

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
        if not self._path.exists():
            return None
        raise NotImplementedError

    def save(self, snapshot: PlanSnapshot) -> None:
        """Persist the snapshot (not implemented yet)."""
        raise NotImplementedError
