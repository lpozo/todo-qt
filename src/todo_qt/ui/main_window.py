"""Main application window."""

from PySide6.QtWidgets import (
    QListView,
    QPushButton,
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
        self.model = TaskListModel(service)
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.add_button = QPushButton("Add task")
        layout = QVBoxLayout(self)
        layout.addWidget(self.list_view)
        layout.addWidget(self.add_button)
