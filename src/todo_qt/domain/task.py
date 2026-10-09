"""Task value types."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import NewType

from todo_qt.domain.errors import (
    EmptyTitleError,
    EndNotAfterStartError,
    InvalidTimeSlotError,
)

TaskId = NewType("TaskId", str)


def normalize_title(raw: str) -> str:
    """Return the stripped title, rejecting empty ones."""
    title = raw.strip()
    if not title:
        raise EmptyTitleError("title must not be empty")
    return title


def _is_minute_precision_naive(value: datetime) -> bool:
    return value.tzinfo is None and value.second == 0 and value.microsecond == 0


@dataclass(frozen=True, slots=True)
class TimeSlot:
    """A start/end time range."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        """Reject aware, imprecise, or non-increasing slots."""
        if not (_is_minute_precision_naive(self.start) and _is_minute_precision_naive(self.end)):
            raise InvalidTimeSlotError("slot times must be naive with minute precision")
        if self.end <= self.start:
            raise EndNotAfterStartError("slot must end after it starts")

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

    def __post_init__(self) -> None:
        """Reject blank titles."""
        if not self.title.strip():
            raise EmptyTitleError("title must not be empty")


@dataclass(frozen=True, slots=True)
class RemovedEntry:
    """A task together with its pre-removal index."""

    index: int
    task: Task


@dataclass(frozen=True, slots=True)
class RemovedTasks:
    """Removed entries, ascending by index."""

    entries: tuple[RemovedEntry, ...]

    def __post_init__(self) -> None:
        """Require non-empty entries with strictly ascending, non-negative indexes."""
        indexes = [entry.index for entry in self.entries]
        if not indexes or indexes[0] < 0:
            raise ValueError("entries must be non-empty with non-negative indexes")
        if any(a >= b for a, b in pairwise(indexes)):
            raise ValueError("entry indexes must be strictly ascending")
