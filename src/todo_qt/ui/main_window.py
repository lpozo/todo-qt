"""Main application window."""

from datetime import datetime

from PySide6.QtCore import QModelIndex, QTime, QTimer
from PySide6.QtWidgets import (
    QLabel,
    QListView,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from todo_qt.domain import TaskId
from todo_qt.services import PlanService
from todo_qt.ui.controller import Notifier, UiController
from todo_qt.ui.messages import startup_message
from todo_qt.ui.task_form import TaskForm
from todo_qt.ui.task_model import TaskListModel

OVERDUE_REFRESH_MS = 15_000
"""Interval of the overdue re-evaluation timer."""


class MainWindow(QWidget):
    """Window showing the task list, a message label, and an inline add form."""

    def __init__(self, service: PlanService, notifier: Notifier | None = None) -> None:
        """Build the window; messages go to `notifier` or the message label."""
        super().__init__()
        self.setWindowTitle("Todo")
        self._service = service
        self._editing_id: TaskId | None = None
        self.message_label = QLabel()
        notify = notifier or self.show_message
        self.controller = UiController(service, notify, self.refresh)
        self.add_form = TaskForm()
        self.add_form.hide()
        self.add_form.submitted.connect(self._on_add_submitted)
        self.model = TaskListModel(service, self.controller.set_done)
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.day_start_edit = QTimeEdit()
        self.day_start_edit.setReadOnly(True)
        self.day_start_edit.setDisplayFormat("HH:mm")
        self.refresh()
        self.overdue_timer = QTimer(self)
        self.overdue_timer.setInterval(OVERDUE_REFRESH_MS)
        self.overdue_timer.timeout.connect(self.refresh_overdue)
        self.overdue_timer.start()
        self.add_button = QPushButton("Add task")
        self.edit_button = QPushButton("Edit task")
        layout = QVBoxLayout(self)
        layout.addWidget(self.day_start_edit)
        layout.addWidget(self.list_view)
        layout.addWidget(self.message_label)
        layout.addWidget(self.add_form)
        layout.addWidget(self.add_button)
        layout.addWidget(self.edit_button)
        self.add_button.clicked.connect(self.open_add_form)
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.list_view.doubleClicked.connect(self.open_edit_form)
        if service.startup_error is not None:
            notify(startup_message(service.startup_error))

    def show_message(self, text: str) -> None:
        """Show a message in the window's message label."""
        self.message_label.setText(text)

    def open_add_form(self) -> None:
        """Show the add form pre-filled with the default slot."""
        self.message_label.clear()
        self._editing_id = None
        slot = self._service.default_slot()
        self.add_form.open_with("", slot.start, slot.end)

    def open_edit_form(self, index: QModelIndex) -> None:
        """Show the form in edit mode, pre-filled with the task at `index`."""
        if not index.isValid():
            return
        task = self._service.plan.tasks[index.row()]
        self.message_label.clear()
        self._editing_id = task.id
        self.add_form.open_with(task.title, task.slot.start, task.slot.end)

    def _on_edit_clicked(self) -> None:
        """Edit the currently selected row, if any."""
        self.open_edit_form(self.list_view.currentIndex())

    def _on_add_submitted(self, title: str, start: datetime, end: datetime) -> None:
        """Add the task, or apply the edit in edit mode; close only when accepted."""
        self.message_label.clear()
        if self._editing_id is not None:
            task_id = self._editing_id
            accepted = self.controller.edit_task(task_id, title, start, end)
            if accepted or not self._has_task(task_id):
                self.add_form.hide()  # also closes when the task vanished meanwhile
                self._editing_id = None
            return
        if self.controller.add_task(title, start, end):
            self.add_form.hide()

    def _has_task(self, task_id: TaskId) -> bool:
        """Return whether the plan still contains `task_id`."""
        return any(task.id == task_id for task in self._service.plan.tasks)

    def refresh(self) -> None:
        """Re-read the plan into the model and the day start control."""
        self.model.refresh()
        day_start = self._service.plan.day_start
        self.day_start_edit.setTime(QTime(day_start.hour, day_start.minute))

    def refresh_overdue(self) -> None:
        """Re-evaluate overdue tasks against the clock."""
        self.model.refresh_overdue()
