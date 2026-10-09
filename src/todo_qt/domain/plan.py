"""The Plan aggregate."""

from dataclasses import dataclass
from datetime import time

from todo_qt.domain.task import Task

DEFAULT_DAY_START: time = time(9, 0)


@dataclass(frozen=True, slots=True)
class Plan:
    """An ordered list of tasks plus the day start."""

    tasks: tuple[Task, ...] = ()
    day_start: time = DEFAULT_DAY_START
