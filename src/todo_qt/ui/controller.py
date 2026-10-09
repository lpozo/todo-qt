"""Qt-free UI controller: the bridge between widgets and the plan service."""

from collections.abc import Callable
from datetime import datetime, time

from todo_qt.domain import DomainError, TaskId, TaskNotFoundError, TimeSlot, normalize_title
from todo_qt.services import ChangeResult, PlanService
from todo_qt.ui.messages import message_for, save_failure_message

Notifier = Callable[[str], None]


class UiController:
    """Runs service commands and reports their outcome to the window."""

    def __init__(
        self, service: PlanService, notifier: Notifier, on_change: Callable[[], None]
    ) -> None:
        self._service = service
        self._notify = notifier
        self._on_change = on_change

    def add_task(self, title: str, start: datetime, end: datetime) -> bool:
        """Add a task; return False (after notifying) if it was rejected."""

        def command() -> ChangeResult:
            clean_title = normalize_title(title)  # first, so its message wins
            return self._service.add_task(clean_title, TimeSlot(start, end))

        return self._run(command)

    def edit_title(self, task_id: TaskId, title: str) -> bool:
        """Rename a task; return False (after notifying) if it was rejected."""
        return self._run(lambda: self._service.edit_title(task_id, normalize_title(title)))

    def reschedule(self, task_id: TaskId, start: datetime, end: datetime) -> bool:
        """Move a task to a new slot; return False (after notifying) if rejected."""
        return self._run(lambda: self._service.reschedule(task_id, TimeSlot(start, end)))

    def edit_task(self, task_id: TaskId, title: str, start: datetime, end: datetime) -> bool:
        """Change a task's title and slot; return False (after notifying) if rejected.

        Both parts are validated before either is applied (the title message wins),
        and only the parts that changed are sent to the service. The two step results
        are merged into one: `changed` if either changed, and at most one save-failure
        message, where the slot step's error wins if both saves fail.
        """

        def command() -> ChangeResult:
            clean_title = normalize_title(title)
            slot = TimeSlot(start, end)
            task = next((t for t in self._service.plan.tasks if t.id == task_id), None)
            if task is None:
                raise TaskNotFoundError(task_id)
            result = ChangeResult(self._service.plan, changed=False)
            if clean_title != task.title:
                result = self._service.edit_title(task_id, clean_title)
            if slot != task.slot:
                moved = self._service.reschedule(task_id, slot)
                result = ChangeResult(
                    moved.plan,
                    changed=result.changed or moved.changed,
                    save_error=moved.save_error or result.save_error,
                )
            return result

        return self._run(command)

    def move_task(self, task_id: TaskId, to_index: int) -> bool:
        """Move a task to its final index; return False (after notifying) if rejected."""
        return self._run(lambda: self._service.move_task(task_id, to_index))

    def set_done(self, task_id: TaskId, done: bool) -> bool:
        """Mark a task done or open; return False (after notifying) if rejected."""
        return self._run(lambda: self._service.set_done(task_id, done))

    def delete_task(self, task_id: TaskId) -> bool:
        """Delete a task (undoable); return False (after notifying) if rejected."""
        return self._run(lambda: self._service.delete_task(task_id))

    def clear_completed(self) -> bool:
        """Delete all done tasks (undoable); a no-op when none are done."""
        return self._run(self._service.clear_completed)

    def set_day_start(self, day_start: time) -> bool:
        """Change the day start (re-chaining the list); a no-op if unchanged."""
        return self._run(lambda: self._service.set_day_start(day_start))

    def undo(self) -> bool:
        """Restore the last removed tasks; a no-op when there is nothing to undo."""
        return self._run(self._service.undo)

    def _run(self, command: Callable[[], ChangeResult]) -> bool:
        """Run a command; notify on errors, refresh on change.

        Return True if accepted; a no-op is accepted too.
        """
        try:
            result = command()
        except DomainError as error:
            self._notify(message_for(error))
            return False
        if result.save_error is not None:
            self._notify(save_failure_message(result.save_error))
        if result.changed:
            self._on_change()
        return True
