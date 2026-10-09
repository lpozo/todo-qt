"""Scheduling helpers."""

from datetime import datetime, timedelta

from todo_qt.domain.task import Task, TimeSlot

DEFAULT_SLOT_DURATION: timedelta = timedelta(minutes=30)


def default_slot(now: datetime) -> TimeSlot:
    """Return the default slot for a new task created at now."""
    raise NotImplementedError


def is_overdue(task: Task, now: datetime) -> bool:
    """Return whether the task is past its end and not done."""
    raise NotImplementedError
