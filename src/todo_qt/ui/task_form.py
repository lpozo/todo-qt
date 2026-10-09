"""Inline form for entering a task's title and time slot."""

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDateTimeEdit, QHBoxLayout, QLineEdit, QPushButton, QWidget

from todo_qt.ui.convert import to_datetime, to_qdatetime

DISPLAY_FORMAT = "yyyy-MM-dd HH:mm"


class TaskForm(QWidget):
    """Title, start, end and a confirm button; emits `submitted` on confirm."""

    submitted = Signal(str, object, object)

    def __init__(self) -> None:
        """Build the form widgets."""
        super().__init__()
        self.title_edit = QLineEdit()
        self.start_edit = QDateTimeEdit()
        self.end_edit = QDateTimeEdit()
        for edit in (self.start_edit, self.end_edit):
            edit.setDisplayFormat(DISPLAY_FORMAT)
            edit.setCalendarPopup(True)
        self.confirm_button = QPushButton("Confirm")
        layout = QHBoxLayout(self)
        for widget in (self.title_edit, self.start_edit, self.end_edit, self.confirm_button):
            layout.addWidget(widget)
        self.confirm_button.clicked.connect(self.confirm)

    def open_with(self, title: str, start: datetime, end: datetime) -> None:
        """Fill the fields, show the form, and focus the title."""
        self.title_edit.setText(title)
        self.start_edit.setDateTime(to_qdatetime(start))
        self.end_edit.setDateTime(to_qdatetime(end))
        self.show()
        self.title_edit.setFocus()

    def values(self) -> tuple[str, datetime, datetime]:
        """Return the title and the naive, minute-precision start and end."""
        return (
            self.title_edit.text(),
            to_datetime(self.start_edit.dateTime()),
            to_datetime(self.end_edit.dateTime()),
        )

    def confirm(self) -> None:
        """Emit `submitted` with the current values."""
        self.submitted.emit(*self.values())
