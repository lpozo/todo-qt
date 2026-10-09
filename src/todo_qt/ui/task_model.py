"""List model exposing the plan's tasks to Qt views."""

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QMimeData,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
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

TASK_MIME_TYPE = "application/x-todo-qt-task-id"
"""Mime type carrying the id of the dragged task."""


def final_index(old: int, drop_row: int, size: int) -> int:
    """Convert a drop insertion point (taken before removal) to the final index.

    `drop_row` -1 means append.
    """
    if drop_row == -1:
        return size - 1
    return drop_row - 1 if drop_row > old else drop_row


class TaskListModel(QAbstractListModel):
    """Read-only list model backed by a PlanService."""

    def __init__(
        self,
        service: PlanService,
        set_done: Callable[[TaskId, bool], bool] | None = None,
        move: Callable[[TaskId, int], bool] | None = None,
    ) -> None:
        """Create the model over the service.

        `set_done` handles check-state edits and `move` handles drops.
        """
        super().__init__()
        self._service = service
        self._set_done = set_done
        self._move = move
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
        """Make rows checkable and draggable; only the root accepts drops."""
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled
        return base | Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802
        """Only moving is supported."""
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:  # noqa: N802
        """Return the mime type carrying a task id."""
        return [TASK_MIME_TYPE]

    def mimeData(  # noqa: N802
        self, indexes: Sequence[QModelIndex]
    ) -> QMimeData:
        """Carry the id of the first dragged task."""
        data = QMimeData()
        # Single selection: only the first valid index is carried.
        for index in indexes:
            if index.isValid() and 0 <= index.row() < self.rowCount():
                task_id = self._service.plan.tasks[index.row()].id
                data.setData(TASK_MIME_TYPE, QByteArray(task_id.encode()))
                break
        return data

    def dropMimeData(  # noqa: N802
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """Move the dragged task to the drop point through the controller."""
        if (
            self._move is None
            or action != Qt.DropAction.MoveAction
            or parent.isValid()
            or not data.hasFormat(TASK_MIME_TYPE)
        ):
            return False
        try:
            task_id = TaskId(bytes(data.data(TASK_MIME_TYPE).data()).decode())
        except UnicodeDecodeError:
            return False
        tasks = self._service.plan.tasks
        old = next((i for i, task in enumerate(tasks) if task.id == task_id), None)
        if old is None:
            return False
        return self._move(task_id, final_index(old, row, len(tasks)))

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
