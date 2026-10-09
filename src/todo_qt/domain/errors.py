"""Domain exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from todo_qt.domain.task import TaskId


class DomainError(Exception):
    """Base class of all domain errors."""


class EmptyTitleError(DomainError):
    """A title is empty or whitespace-only."""


class InvalidTimeSlotError(DomainError):
    """A slot datetime is aware or has seconds."""


class EndNotAfterStartError(InvalidTimeSlotError):
    """A slot ends at or before its start."""


class InvalidDayStartError(DomainError):
    """A day start is aware or has seconds."""


class NaiveDatetimeRequiredError(DomainError, ValueError):
    """A now argument is timezone-aware."""


class TaskNotFoundError(DomainError):
    """A task id is not in the plan."""

    def __init__(self, task_id: TaskId) -> None:
        super().__init__(task_id)
        self.task_id = task_id


class DuplicateTaskIdError(DomainError):
    """A task id is already in the plan."""

    def __init__(self, task_id: TaskId) -> None:
        super().__init__(task_id)
        self.task_id = task_id


class IndexOutOfRangeError(DomainError, IndexError):
    """A target index is outside the plan."""

    def __init__(self, index: int, size: int) -> None:
        super().__init__(index, size)
        self.index = index
        self.size = size
