"""Main application window."""

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QListView,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from todo_qt.services import PlanService
from todo_qt.ui.task_model import TaskListModel


class MainWindow(QWidget):
    """Window showing the task list and an inert Add task button."""

    def __init__(self, service: PlanService) -> None:
        """Build the window for the given service."""
        super().__init__()
        self.setWindowTitle("Todo")
        self._service = service
        self.model = TaskListModel(service)
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.day_start_edit = QTimeEdit()
        self.day_start_edit.setReadOnly(True)
        self.day_start_edit.setDisplayFormat("HH:mm")
        self.refresh()
        self.add_button = QPushButton("Add task")
        layout = QVBoxLayout(self)
        layout.addWidget(self.day_start_edit)
        layout.addWidget(self.list_view)
        layout.addWidget(self.add_button)

    def refresh(self) -> None:
        """Re-read the plan into the model and the day start control."""
        self.model.refresh()
        day_start = self._service.plan.day_start
        self.day_start_edit.setTime(QTime(day_start.hour, day_start.minute))
