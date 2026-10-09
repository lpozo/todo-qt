"""Application service that owns the plan and its auto-save."""

from dataclasses import dataclass
from datetime import datetime, time

from todo_qt.domain import Plan, RemovedTasks, TaskId, TimeSlot, default_slot, is_overdue
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
        return default_slot(self._clock())

    def is_overdue(self, task_id: TaskId) -> bool:
        """Return whether the task is overdue now."""
        return is_overdue(self._plan.get(task_id), self._clock())

    def overdue_ids(self) -> frozenset[TaskId]:
        """Return the ids of all overdue tasks."""
        now = self._clock()
        return frozenset(task.id for task in self._plan.tasks if is_overdue(task, now))

    def add_task(self, title: str, slot: TimeSlot) -> ChangeResult:
        """Append a task."""
        task_id = self._new_id()
        return self._commit(self._plan.add(task_id, title, slot), task_id=task_id)

    def _commit(self, new_plan: Plan, *, task_id: TaskId | None = None) -> ChangeResult:
        """Adopt new_plan, save it if it changed, and report any write failure."""
        changed = new_plan != self._plan
        save_error: StoreWriteError | None = None
        if changed:
            self._plan = new_plan
            try:
                self._store.save(new_plan)
            except StoreWriteError as error:
                save_error = error
        return ChangeResult(self._plan, changed, save_error, task_id)

    def edit_title(self, task_id: TaskId, title: str) -> ChangeResult:
        """Change a task's title."""
        return self._commit(self._plan.edit_title(task_id, title))

    def reschedule(self, task_id: TaskId, slot: TimeSlot) -> ChangeResult:
        """Change a task's slot."""
        return self._commit(self._plan.reschedule(task_id, slot))

    def set_done(self, task_id: TaskId, done: bool) -> ChangeResult:
        """Set a task's done flag."""
        return self._commit(self._plan.set_done(task_id, done))

    def delete_task(self, task_id: TaskId) -> ChangeResult:
        """Delete a task, remembering it for undo."""
        new_plan, removed = self._plan.delete(task_id)
        self._undo_slot = removed
        return self._commit(new_plan)

    def clear_completed(self) -> ChangeResult:
        """Delete all done tasks, remembering them for undo."""
        new_plan, removed = self._plan.clear_completed()
        if removed is None:
            return self._commit(new_plan)
        self._undo_slot = removed
        return self._commit(new_plan)

    def undo(self) -> ChangeResult:
        """Restore the last removed tasks."""
        if self._undo_slot is None:
            return self._commit(self._plan)
        new_plan = self._plan.restore(self._undo_slot)
        self._undo_slot = None
        return self._commit(new_plan)

    def move_task(self, task_id: TaskId, to_index: int) -> ChangeResult:
        """Move a task and re-chain the timeline."""
        raise NotImplementedError

    def set_day_start(self, day_start: time) -> ChangeResult:
        """Change the day start and re-chain the timeline."""
        raise NotImplementedError
