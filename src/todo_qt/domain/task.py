"""Task value types."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NewType

TaskId = NewType("TaskId", str)


def normalize_title(raw: str) -> str:
    """Return the stripped title, rejecting empty ones."""
    raise NotImplementedError


@dataclass(frozen=True, slots=True)
class TimeSlot:
    """A start/end time range."""

    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        """Length of the slot."""
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Task:
    """A scheduled task."""

    id: TaskId
    title: str
    slot: TimeSlot
    done: bool = False


@dataclass(frozen=True, slots=True)
class RemovedEntry:
    """A task together with its pre-removal index."""

    index: int
    task: Task


@dataclass(frozen=True, slots=True)
class RemovedTasks:
    """Removed entries, ascending by index."""

    entries: tuple[RemovedEntry, ...]
