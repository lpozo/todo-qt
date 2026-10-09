"""Framework-free domain model."""

from todo_qt.domain.errors import (
    DomainError,
    DuplicateTaskIdError,
    EmptyTitleError,
    EndNotAfterStartError,
    IndexOutOfRangeError,
    InvalidDayStartError,
    InvalidTimeSlotError,
    NaiveDatetimeRequiredError,
    TaskNotFoundError,
)
from todo_qt.domain.plan import DEFAULT_DAY_START, Plan
from todo_qt.domain.schedule import DEFAULT_SLOT_DURATION, default_slot, is_overdue
from todo_qt.domain.task import (
    RemovedEntry,
    RemovedTasks,
    Task,
    TaskId,
    TimeSlot,
    normalize_title,
)

__all__ = [
    "DEFAULT_DAY_START",
    "DEFAULT_SLOT_DURATION",
    "DomainError",
    "DuplicateTaskIdError",
    "EmptyTitleError",
    "EndNotAfterStartError",
    "IndexOutOfRangeError",
    "InvalidDayStartError",
    "InvalidTimeSlotError",
    "NaiveDatetimeRequiredError",
    "Plan",
    "RemovedEntry",
    "RemovedTasks",
    "Task",
    "TaskId",
    "TaskNotFoundError",
    "TimeSlot",
    "default_slot",
    "is_overdue",
    "normalize_title",
]
