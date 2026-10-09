"""The Plan aggregate."""

from dataclasses import dataclass, replace
from datetime import datetime, time

from todo_qt.domain.errors import (
    DuplicateTaskIdError,
    IndexOutOfRangeError,
    InvalidDayStartError,
    TaskNotFoundError,
)
from todo_qt.domain.task import (
    RemovedEntry,
    RemovedTasks,
    Task,
    TaskId,
    TimeSlot,
    normalize_title,
)

DEFAULT_DAY_START: time = time(9, 0)


def _check_day_start(day_start: time) -> None:
    if day_start.tzinfo is not None or day_start.second or day_start.microsecond:
        raise InvalidDayStartError(day_start)


def _rechain(tasks: tuple[Task, ...], first_start: datetime | None = None) -> tuple[Task, ...]:
    """Chain tasks end to start, optionally moving the first to `first_start`."""
    result: list[Task] = []
    cursor = first_start
    for task in tasks:
        start = task.slot.start if cursor is None else cursor
        end = start + (task.slot.end - task.slot.start)
        result.append(replace(task, slot=TimeSlot(start, end)))
        cursor = end
    return tuple(result)


@dataclass(frozen=True, slots=True)
class Plan:
    """An ordered list of tasks plus the day start."""

    tasks: tuple[Task, ...] = ()
    day_start: time = DEFAULT_DAY_START

    def __post_init__(self) -> None:
        """Reject an invalid day start and duplicate task ids."""
        _check_day_start(self.day_start)
        seen: set[TaskId] = set()
        for task in self.tasks:
            if task.id in seen:
                raise DuplicateTaskIdError(task.id)
            seen.add(task.id)

    def index_of(self, task_id: TaskId) -> int:
        """Return the 0-based index of a task."""
        for index, task in enumerate(self.tasks):
            if task.id == task_id:
                return index
        raise TaskNotFoundError(task_id)

    def get(self, task_id: TaskId) -> Task:
        """Return the task with the given id."""
        return self.tasks[self.index_of(task_id)]

    def add(self, task_id: TaskId, title: str, slot: TimeSlot) -> Plan:
        """Return a new plan with a not-done task appended at the bottom."""
        task = Task(task_id, normalize_title(title), slot, done=False)
        return Plan((*self.tasks, task), self.day_start)

    def _with_task(self, task: Task) -> Plan:
        index = self.index_of(task.id)
        return Plan((*self.tasks[:index], task, *self.tasks[index + 1 :]), self.day_start)

    def edit_title(self, task_id: TaskId, title: str) -> Plan:
        """Return a new plan with the task's title replaced."""
        task = self.get(task_id)
        return self._with_task(replace(task, title=normalize_title(title)))

    def reschedule(self, task_id: TaskId, slot: TimeSlot) -> Plan:
        """Return a new plan with the task's slot replaced."""
        return self._with_task(replace(self.get(task_id), slot=slot))

    def set_done(self, task_id: TaskId, done: bool) -> Plan:
        """Return a new plan with the task's done flag set."""
        return self._with_task(replace(self.get(task_id), done=done))

    def delete(self, task_id: TaskId) -> tuple[Plan, RemovedTasks]:
        """Return a new plan without the task, plus what was removed."""
        index = self.index_of(task_id)
        removed = RemovedTasks((RemovedEntry(index, self.tasks[index]),))
        return Plan((*self.tasks[:index], *self.tasks[index + 1 :]), self.day_start), removed

    def clear_completed(self) -> tuple[Plan, RemovedTasks | None]:
        """Return a new plan without done tasks, plus what was removed (None if none)."""
        entries = tuple(RemovedEntry(i, t) for i, t in enumerate(self.tasks) if t.done)
        if not entries:
            return self, None
        open_tasks = tuple(t for t in self.tasks if not t.done)
        return Plan(open_tasks, self.day_start), RemovedTasks(entries)

    def restore(self, removed: RemovedTasks) -> Plan:
        """Return a new plan with removed tasks re-inserted at their old indexes."""
        tasks = list(self.tasks)
        for entry in removed.entries:
            tasks.insert(min(entry.index, len(tasks)), entry.task)
        return Plan(tuple(tasks), self.day_start)

    def move(self, task_id: TaskId, to_index: int) -> Plan:
        """Return a new plan with the task at its final index and the timeline re-chained."""
        if not 0 <= to_index < len(self.tasks):
            raise IndexOutOfRangeError(to_index, len(self.tasks))
        old = self.index_of(task_id)
        if to_index == old:
            return self
        moved = self.tasks[old]
        rest = (*self.tasks[:old], *self.tasks[old + 1 :])
        reordered = (*rest[:to_index], moved, *rest[to_index:])
        if to_index == 0 or old == 0:
            anchor_date = (
                self.tasks[0].slot.start.date() if to_index == 0 else rest[0].slot.start.date()
            )
            return Plan(
                _rechain(reordered, datetime.combine(anchor_date, self.day_start)), self.day_start
            )
        head = reordered[:to_index]
        return Plan((*head, *_rechain(reordered[to_index:], head[-1].slot.end)), self.day_start)

    def set_day_start(self, day_start: time) -> Plan:
        """Return a new plan with a new day start and the timeline re-chained from it."""
        _check_day_start(day_start)
        if day_start == self.day_start:
            return self
        if not self.tasks:
            return Plan(self.tasks, day_start)
        first_date = self.tasks[0].slot.start.date()
        return Plan(_rechain(self.tasks, datetime.combine(first_date, day_start)), day_start)
