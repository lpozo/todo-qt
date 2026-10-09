"""List model exposing the plan's tasks to Qt views."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from todo_qt.domain import TaskId
from todo_qt.services import PlanService

_ROOT = QModelIndex()
_TIME_FORMAT = "%Y-%m-%d %H:%M"

DONE_ROLE: int = Qt.ItemDataRole.UserRole + 1
"""Custom role: whether the task is done (bool)."""

OVERDUE_ROLE: int = Qt.ItemDataRole.UserRole + 2
"""Custom role: whether the task is overdue (bool)."""

_OVERDUE_BRUSH = QBrush(QColor(255, 200, 200))


class TaskListModel(QAbstractListModel):
    """Read-only list model backed by a PlanService."""

    def __init__(
        self, service: PlanService, set_done: Callable[[TaskId, bool], bool] | None = None
    ) -> None:
        """Create the model over the service; `set_done` handles check-state edits."""
        super().__init__()
        self._service = service
        self._set_done = set_done
        self._overdue: frozenset[TaskId] = service.overdue_ids()

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
        if role == OVERDUE_ROLE:
            return task.id in self._overdue
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if task.done else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.FontRole and task.done:
            font = QFont()
            font.setStrikeOut(True)
            return font
        if role == Qt.ItemDataRole.BackgroundRole and task.id in self._overdue:
            return _OVERDUE_BRUSH
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        """Make rows checkable so the done state can be toggled."""
        base = super().flags(index)
        return base | Qt.ItemFlag.ItemIsUserCheckable if index.isValid() else base

    def setData(  # noqa: N802
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Toggle done through the controller when the check state is set."""
        if role != Qt.ItemDataRole.CheckStateRole or self._set_done is None:
            return False
        if not index.isValid() or not 0 <= index.row() < self.rowCount():
            return False
        task = self._service.plan.tasks[index.row()]
        # The controller's refresh resets the model, which clears the view selection.
        return self._set_done(task.id, Qt.CheckState(value) == Qt.CheckState.Checked)

    def refresh_overdue(self) -> None:
        """Emit dataChanged for all rows only if the overdue set changed."""
        overdue = self._service.overdue_ids()
        if overdue == self._overdue:
            return
        self._overdue = overdue
        count = self.rowCount()
        if count:
            self.dataChanged.emit(self.index(0), self.index(count - 1))

    def refresh(self) -> None:
        """Reset the model so views re-read service.plan."""
        self.beginResetModel()
        self._overdue = self._service.overdue_ids()
        self.endResetModel()
