"""Tests for Plan.delete, Plan.clear_completed, and Plan.restore."""

import pytest

from tests.task_list.fakes import T, make_plan, make_slot, make_task
from todo_qt.domain.errors import DuplicateTaskIdError, TaskNotFoundError
from todo_qt.domain.task import RemovedEntry, RemovedTasks, TaskId


def test_delete_removes_task_without_touching_others() -> None:
    a = make_task("a", "A", make_slot(T(9), T(10)))
    b = make_task("b", "B", make_slot(T(10), T(11)))
    c = make_task("c", "C", make_slot(T(11), T(12)))

    result, removed = make_plan(a, b, c).delete(TaskId("b"))

    assert (result.tasks, removed) == ((a, c), RemovedTasks((RemovedEntry(1, b),)))


def test_delete_unknown_id_raises() -> None:
    with pytest.raises(TaskNotFoundError):
        make_plan(make_task("a")).delete(TaskId("zz"))


def test_clear_completed_removes_only_done_tasks() -> None:
    a = make_task("a", "A", make_slot(T(9), T(10)))
    b = make_task("b", "B", make_slot(T(10), T(11)), done=True)
    c = make_task("c", "C", make_slot(T(11), T(12)))
    d = make_task("d", "D", make_slot(T(12), T(13)), done=True)

    result, removed = make_plan(a, b, c, d).clear_completed()

    assert (result.tasks, removed) == (
        (a, c),
        RemovedTasks((RemovedEntry(1, b), RemovedEntry(3, d))),
    )


def test_clear_completed_with_nothing_done_returns_none() -> None:
    plan = make_plan(make_task("a"), make_task("b"))

    assert plan.clear_completed() == (plan, None)


def test_restore_reinserts_deleted_task_at_previous_index() -> None:
    a = make_task("a", "A", make_slot(T(9), T(10)))
    b = make_task("b", "B", make_slot(T(10), T(11)))
    c = make_task("c", "C", make_slot(T(11), T(12)))

    result = make_plan(a, c).restore(RemovedTasks((RemovedEntry(1, b),)))

    assert result.tasks == (a, b, c)


def test_restore_reinserts_cleared_tasks_at_previous_positions() -> None:
    a, b, c, d = (make_task(i) for i in "abcd")
    removed = RemovedTasks((RemovedEntry(1, b), RemovedEntry(3, d)))

    result = make_plan(a, c).restore(removed)

    assert result.tasks == (a, b, c, d)


def test_restore_after_add_inserts_at_old_index_not_at_end() -> None:
    a, b, c, d = (make_task(i) for i in "abcd")

    result = make_plan(b, c, d).restore(RemovedTasks((RemovedEntry(0, a),)))

    assert result.tasks == (a, b, c, d)


def test_restore_clamps_index_beyond_current_length() -> None:
    a, z = make_task("a"), make_task("z")

    result = make_plan(a).restore(RemovedTasks((RemovedEntry(5, z),)))

    assert result.tasks == (a, z)


def test_restore_keeps_done_flag_and_times() -> None:
    x = make_task("x", "X", make_slot(T(9), T(10)), done=True)
    neighbour = make_task("n", "N", make_slot(T(14), T(15)))

    result = make_plan(neighbour).restore(RemovedTasks((RemovedEntry(0, x),)))

    assert result.tasks == (x, neighbour)


def test_restore_clamps_each_entry_against_growing_list() -> None:
    a, b, c, d = (make_task(i) for i in "abcd")
    removed = RemovedTasks((RemovedEntry(1, b), RemovedEntry(2, c), RemovedEntry(9, d)))

    result = make_plan(a).restore(removed)

    assert result.tasks == (a, b, c, d)


def test_restore_duplicate_after_valid_entry_raises_without_partial_result() -> None:
    a, x = make_task("a"), make_task("x")
    plan = make_plan(a)

    with pytest.raises(DuplicateTaskIdError):
        plan.restore(RemovedTasks((RemovedEntry(0, x), RemovedEntry(1, a))))

    assert plan.tasks == (a,)


def test_restore_duplicate_id_raises() -> None:
    a = make_task("a")

    with pytest.raises(DuplicateTaskIdError):
        make_plan(a).restore(RemovedTasks((RemovedEntry(0, a),)))
