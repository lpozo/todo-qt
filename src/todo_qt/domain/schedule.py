"""Scheduling helpers."""

from datetime import datetime, timedelta

from todo_qt.domain.errors import NaiveDatetimeRequiredError
from todo_qt.domain.task import Task, TimeSlot

DEFAULT_SLOT_DURATION: timedelta = timedelta(minutes=30)


def default_slot(now: datetime) -> TimeSlot:
    """Return the default slot for a new task created at now."""
    _require_naive(now)
    start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return TimeSlot(start, start + DEFAULT_SLOT_DURATION)


def is_overdue(task: Task, now: datetime) -> bool:
    """Return whether the task is past its end and not done."""
    _require_naive(now)
    return not task.done and task.slot.end < now


def _require_naive(now: datetime) -> None:
    if now.tzinfo is not None:
        raise NaiveDatetimeRequiredError
