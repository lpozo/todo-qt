"""The Plan aggregate."""

from dataclasses import dataclass, replace
from datetime import time

from todo_qt.domain.errors import DuplicateTaskIdError, TaskNotFoundError
from todo_qt.domain.task import Task, TaskId, TimeSlot, normalize_title

DEFAULT_DAY_START: time = time(9, 0)


@dataclass(frozen=True, slots=True)
class Plan:
    """An ordered list of tasks plus the day start."""

    tasks: tuple[Task, ...] = ()
    day_start: time = DEFAULT_DAY_START

    def __post_init__(self) -> None:
        """Reject duplicate task ids."""
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
