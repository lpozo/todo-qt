"""List model exposing the plan's tasks to Qt views."""

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt

from todo_qt.services import PlanService

_ROOT = QModelIndex()
_TIME_FORMAT = "%Y-%m-%d %H:%M"

DONE_ROLE: int = Qt.ItemDataRole.UserRole + 1
"""Custom role: whether the task is done (bool)."""


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

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return the row text for DisplayRole and the done flag for DONE_ROLE."""
        if not index.isValid() or not 0 <= index.row() < self.rowCount():
            return None
        task = self._service.plan.tasks[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            slot = task.slot
            return (
                f"{task.title}\n{slot.start.strftime(_TIME_FORMAT)} - "
                f"{slot.end.strftime(_TIME_FORMAT)}"
            )
        if role == DONE_ROLE:
            return task.done
        return None

    def refresh(self) -> None:
        """Reset the model so views re-read service.plan."""
        self.beginResetModel()
        self.endResetModel()
