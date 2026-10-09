"""List model exposing the plan's tasks to Qt views."""

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex

from todo_qt.services import PlanService

_ROOT = QModelIndex()


class TaskListModel(QAbstractListModel):
    """Read-only list model backed by a PlanService."""

    def __init__(self, service: PlanService) -> None:
        """Create the model over the given service."""
        super().__init__()
        self._service = service

    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex = _ROOT
    ) -> int:
        """Return the number of tasks in the current plan."""
        if parent.isValid():
            return 0
        return len(self._service.plan.tasks)
