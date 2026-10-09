"""Application service that owns the plan and its auto-save."""

from dataclasses import dataclass
from datetime import datetime, time

from todo_qt.domain import Plan, RemovedTasks, TaskId, TimeSlot
from todo_qt.services.errors import StoreCorruptError, StoreWriteError
from todo_qt.services.ports import Clock, IdFactory, PlanStore


@dataclass(frozen=True, slots=True)
class ChangeResult:
    """Outcome of a command."""

    plan: Plan
    changed: bool
    save_error: StoreWriteError | None = None
    task_id: TaskId | None = None


class PlanService:
    """Owns the current plan, the undo slot, and auto-save."""

    def __init__(self, store: PlanStore, clock: Clock, new_id: IdFactory) -> None:
        self._store = store
        self._clock = clock
        self._new_id = new_id
        self._undo_slot: RemovedTasks | None = None
        self._startup_error: StoreCorruptError | None = None
        self._plan = Plan()
        try:
            loaded = store.load()
        except StoreCorruptError as error:
            self._startup_error = error
        else:
            if loaded is not None:
                self._plan = loaded

    @property
    def plan(self) -> Plan:
        """The current plan."""
        return self._plan

    @property
    def startup_error(self) -> StoreCorruptError | None:
        """The corruption error captured at startup, if any."""
        return self._startup_error

    @property
    def can_undo(self) -> bool:
        """Whether the undo slot is non-empty."""
        return self._undo_slot is not None

    @property
    def can_clear_completed(self) -> bool:
        """Whether any task is done."""
        return any(task.done for task in self._plan.tasks)

    def now(self) -> datetime:
        """Return the injected clock's current time."""
        return self._clock()

    def default_slot(self) -> TimeSlot:
        """Return the prefilled slot for a new task."""
        raise NotImplementedError

    def is_overdue(self, task_id: TaskId) -> bool:
        """Return whether the task is overdue now."""
        raise NotImplementedError

    def overdue_ids(self) -> frozenset[TaskId]:
        """Return the ids of all overdue tasks."""
        raise NotImplementedError

    def add_task(self, title: str, slot: TimeSlot) -> ChangeResult:
        """Append a task."""
        raise NotImplementedError

    def edit_title(self, task_id: TaskId, title: str) -> ChangeResult:
        """Change a task's title."""
        raise NotImplementedError

    def reschedule(self, task_id: TaskId, slot: TimeSlot) -> ChangeResult:
        """Change a task's slot."""
        raise NotImplementedError

    def set_done(self, task_id: TaskId, done: bool) -> ChangeResult:
        """Set a task's done flag."""
        raise NotImplementedError

    def delete_task(self, task_id: TaskId) -> ChangeResult:
        """Delete a task, remembering it for undo."""
        raise NotImplementedError

    def clear_completed(self) -> ChangeResult:
        """Delete all done tasks, remembering them for undo."""
        raise NotImplementedError

    def undo(self) -> ChangeResult:
        """Restore the last removed tasks."""
        raise NotImplementedError

    def move_task(self, task_id: TaskId, to_index: int) -> ChangeResult:
        """Move a task and re-chain the timeline."""
        raise NotImplementedError

    def set_day_start(self, day_start: time) -> ChangeResult:
        """Change the day start and re-chain the timeline."""
        raise NotImplementedError
