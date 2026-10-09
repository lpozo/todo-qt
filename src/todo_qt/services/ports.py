"""Ports the plan service depends on."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from todo_qt.domain import Plan, TaskId

type PlanSnapshot = Plan
type Clock = Callable[[], datetime]
type IdFactory = Callable[[], TaskId]


class PlanStore(Protocol):
    """Persistence port for the plan."""

    def load(self) -> PlanSnapshot | None:
        """Return the saved plan, or None if nothing was ever saved."""
        ...

    def save(self, snapshot: PlanSnapshot) -> None:
        """Atomically persist the snapshot."""
        ...
