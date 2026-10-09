"""Application entry point for the Qt UI."""

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from todo_qt.services import PlanService
from todo_qt.ui.main_window import MainWindow


def run_app(service: PlanService) -> int:
    """Show the main window and run the event loop; return the exit code."""
    app = QCoreApplication.instance() or QApplication(sys.argv)
    window = MainWindow(service)
    window.show()
    return app.exec()
