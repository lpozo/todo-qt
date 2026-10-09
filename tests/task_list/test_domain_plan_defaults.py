"""Spec example: default day start."""

from datetime import time

from todo_qt.domain import Plan


def test_default_day_start_is_nine_oclock() -> None:
    plan = Plan()

    assert plan.day_start == time(9, 0)


def test_errors_module_does_not_import_task_module_at_runtime() -> None:
    from todo_qt.domain import errors

    assert "TaskId" not in vars(errors)
