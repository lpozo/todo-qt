"""Qt-free UI controller: the bridge between widgets and the plan service."""

from collections.abc import Callable
from datetime import datetime

from todo_qt.domain import DomainError, TimeSlot, normalize_title
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

    def _run(self, command: Callable[[], ChangeResult]) -> bool:
        """Run a command; notify on errors, refresh on change, return True if accepted."""
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
