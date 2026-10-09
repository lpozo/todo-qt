"""Tests for Plan.move: the timeline cascade."""

from collections import Counter
from datetime import date, datetime, time, timedelta
from itertools import pairwise

import pytest
from hypothesis import event, given
from hypothesis import strategies as st

from todo_qt.domain import IndexOutOfRangeError, Plan, Task, TaskId, TaskNotFoundError, TimeSlot

from .fakes import FRI, T, make_plan, make_slot, make_task

SAT = date(2026, 1, 3)


def times(plan: Plan) -> list[tuple[str, object, object]]:
    """Return (id, start, end) for each task."""
    return [(t.id, t.slot.start, t.slot.end) for t in plan.tasks]


def slot(sh: int, sm: int, eh: int, em: int, *, day: date = FRI) -> TimeSlot:
    """Build a slot on `day`."""
    return make_slot(T(sh, sm, day=day), T(eh, em, day=day))


def test_move_into_middle_rechains_tail() -> None:
    plan = make_plan(
        make_task("A", slot=slot(9, 0, 10, 0)),
        make_task("B", slot=slot(10, 0, 11, 30)),
        make_task("C", slot=slot(14, 0, 14, 30)),
    )

    result = plan.move(TaskId("C"), 1)

    assert times(result) == [
        ("A", T(9), T(10)),
        ("C", T(10), T(10, 30)),
        ("B", T(10, 30), T(12)),
    ]


def test_move_keeps_tasks_above_destination_unchanged() -> None:
    a = make_task("A", slot=slot(9, 0, 10, 0))
    b = make_task("B", slot=slot(10, 0, 11, 0))
    c = make_task("C", slot=slot(11, 0, 12, 0))
    d = make_task("D", slot=slot(13, 0, 14, 0))

    result = make_plan(a, b, c, d).move(TaskId("D"), 2)

    assert result.tasks[:2] == (a, b)
    assert times(result)[2:] == [("D", T(11), T(12)), ("C", T(12), T(13))]


def test_move_to_top_starts_at_day_start_on_old_first_tasks_date() -> None:
    plan = make_plan(
        make_task("A", slot=slot(10, 0, 11, 0)),
        make_task("B", slot=slot(11, 0, 12, 0)),
        make_task("C", slot=slot(15, 0, 15, 30)),
        day_start=time(9, 0),
    )

    result = plan.move(TaskId("C"), 0)

    assert times(result) == [
        ("C", T(9), T(9, 30)),
        ("A", T(9, 30), T(10, 30)),
        ("B", T(10, 30), T(11, 30)),
    ]


def test_move_to_top_uses_date_of_previous_first_task_not_moved_task() -> None:
    plan = make_plan(
        make_task("A", slot=slot(10, 0, 11, 0, day=SAT)),
        make_task("C", slot=slot(15, 0, 15, 30)),
        day_start=time(9, 0),
    )

    result = plan.move(TaskId("C"), 0)

    assert times(result) == [
        ("C", T(9, day=SAT), T(9, 30, day=SAT)),
        ("A", T(9, 30, day=SAT), T(10, 30, day=SAT)),
    ]


def test_move_rechains_done_task_and_keeps_done_flag() -> None:
    plan = make_plan(
        make_task("A", slot=slot(9, 0, 10, 0)),
        make_task("B", slot=slot(10, 0, 11, 0), done=True),
        make_task("C", slot=slot(12, 0, 13, 0)),
    )

    result = plan.move(TaskId("C"), 1)

    assert times(result)[1:] == [("C", T(10), T(11)), ("B", T(11), T(12))]
    assert result.get(TaskId("B")).done is True


def test_move_cascade_crosses_midnight() -> None:
    plan = make_plan(
        make_task("A", slot=slot(22, 0, 23, 0)),
        make_task("B", slot=slot(23, 0, 23, 45)),
        make_task("C", slot=slot(9, 0, 10, 0)),
    )

    result = plan.move(TaskId("C"), 1)

    assert times(result)[1:] == [
        ("C", T(23), T(0, day=SAT)),
        ("B", T(0, day=SAT), T(0, 45, day=SAT)),
    ]


def test_move_to_own_position_is_noop() -> None:
    plan = make_plan(
        make_task("A", slot=slot(9, 0, 10, 0)),
        make_task("B", slot=slot(10, 0, 11, 0)),
        make_task("C", slot=slot(14, 0, 15, 0)),
    )

    assert plan.move(TaskId("B"), 1) == plan


def test_move_first_task_to_end_rechains_from_new_first() -> None:
    plan = make_plan(
        make_task("A", slot=slot(9, 0, 10, 0)),
        make_task("B", slot=slot(10, 0, 11, 0)),
        make_task("C", slot=slot(11, 0, 12, 0)),
        day_start=time(9, 0),
    )

    result = plan.move(TaskId("A"), 2)

    assert times(result) == [
        ("B", T(9), T(10)),
        ("C", T(10), T(11)),
        ("A", T(11), T(12)),
    ]


def test_move_first_task_down_snaps_new_first_to_day_start() -> None:
    plan = make_plan(
        make_task("A", slot=slot(9, 0, 10, 0)),
        make_task("B", slot=slot(10, 30, 11, 30)),
        make_task("C", slot=slot(12, 0, 13, 0)),
        day_start=time(9, 0),
    )

    result = plan.move(TaskId("A"), 1)

    assert times(result) == [
        ("B", T(9), T(10)),
        ("A", T(10), T(11)),
        ("C", T(11), T(12)),
    ]


def test_move_first_task_down_uses_new_first_tasks_own_date() -> None:
    plan = make_plan(
        make_task("A", slot=slot(9, 0, 10, 0)),
        make_task("B", slot=slot(10, 30, 11, 30, day=SAT)),
        day_start=time(9, 0),
    )

    result = plan.move(TaskId("A"), 1)

    assert times(result) == [
        ("B", T(9, day=SAT), T(10, day=SAT)),
        ("A", T(10, day=SAT), T(11, day=SAT)),
    ]


def test_move_non_first_task_down_leaves_tasks_above_untouched() -> None:
    a = make_task("A", slot=slot(8, 0, 9, 0))
    b = make_task("B", slot=slot(10, 0, 11, 0))
    c = make_task("C", slot=slot(11, 0, 12, 0))
    d = make_task("D", slot=slot(13, 0, 14, 0))

    result = make_plan(a, b, c, d, day_start=time(9, 0)).move(TaskId("B"), 2)

    assert [t.id for t in result.tasks] == ["A", "C", "B", "D"]
    assert result.tasks[:2] == (a, c)
    assert times(result)[2:] == [("B", T(12), T(13)), ("D", T(13), T(14))]


@pytest.mark.parametrize("index", [3, -1])
def test_move_index_out_of_range_raises(index: int) -> None:
    plan = make_plan(make_task("A"), make_task("B"), make_task("C"))

    with pytest.raises(IndexOutOfRangeError) as excinfo:
        plan.move(TaskId("A"), index)

    assert (excinfo.value.index, excinfo.value.size) == (index, 3)


@pytest.mark.parametrize("index", [1, -1])
def test_move_in_single_task_plan_out_of_range_raises(index: int) -> None:
    plan = make_plan(make_task("A"))

    with pytest.raises(IndexOutOfRangeError) as excinfo:
        plan.move(TaskId("A"), index)

    assert (excinfo.value.index, excinfo.value.size) == (index, 1)


def test_move_in_single_task_plan_to_zero_is_noop() -> None:
    plan = make_plan(make_task("A"))

    assert plan.move(TaskId("A"), 0) == plan


def test_move_on_empty_plan_raises_index_out_of_range() -> None:
    with pytest.raises(IndexOutOfRangeError):
        Plan().move(TaskId("A"), 0)


def test_move_first_task_to_index_zero_is_noop() -> None:
    plan = make_plan(
        make_task("A", slot=slot(10, 0, 11, 0)),
        make_task("B", slot=slot(14, 0, 15, 0)),
    )

    assert plan.move(TaskId("A"), 0) == plan


def test_move_non_first_task_to_last_index_rechains_it_at_the_end() -> None:
    plan = make_plan(
        make_task("A", slot=slot(9, 0, 10, 0)),
        make_task("B", slot=slot(10, 0, 11, 0)),
        make_task("C", slot=slot(15, 0, 16, 0)),
    )

    result = plan.move(TaskId("B"), 2)

    assert times(result) == [("A", T(9), T(10)), ("C", T(15), T(16)), ("B", T(16), T(17))]


def test_move_unknown_id_raises() -> None:
    plan = make_plan(make_task("A"))

    with pytest.raises(TaskNotFoundError):
        plan.move(TaskId("zz"), 0)


def summary(plan: Plan) -> Counter[tuple[str, str, timedelta, bool]]:
    """Multiset of (id, title, duration, done)."""
    return Counter((t.id, t.title, t.slot.end - t.slot.start, t.done) for t in plan.tasks)


def test_move_preserves_durations_titles_and_ids() -> None:
    plan = make_plan(
        make_task("A", "a", slot(9, 0, 10, 0)),
        make_task("B", "b", slot(10, 0, 11, 30), done=True),
        make_task("C", "c", slot(14, 0, 14, 30)),
    )

    assert summary(plan.move(TaskId("A"), 2)) == summary(plan)


@st.composite
def plans(draw: st.DrawFn) -> Plan:
    """A plan of 1-8 valid tasks with arbitrary dates, times, gaps and durations."""
    size = draw(st.integers(1, 8))
    tasks = []
    for n in range(size):
        start = datetime(2026, 1, 1) + timedelta(
            days=draw(st.integers(0, 3)), minutes=draw(st.integers(0, 1439))
        )
        duration = timedelta(minutes=draw(st.integers(1, 1500)))
        tasks.append(
            make_task(f"t{n}", f"title {n}", make_slot(start, start + duration), done=n % 2 == 1)
        )
    day_start = time(draw(st.integers(0, 23)), draw(st.integers(0, 59)))
    return make_plan(*tasks, day_start=day_start)


def assert_chained(tasks: tuple[Task, ...]) -> None:
    """Assert each task starts where the one above ends."""
    for above, below in pairwise(tasks):
        assert below.slot.start == above.slot.end


@given(plan=plans(), data=st.data())
def test_move_follows_the_cascade_rules_for_any_plan(plan: Plan, data: st.DataObject) -> None:
    size = len(plan.tasks)
    old = data.draw(st.integers(0, size - 1))
    i = data.draw(st.integers(0, size - 1))
    moved = plan.tasks[old]
    reordered = (*plan.tasks[:old], *plan.tasks[old + 1 :])
    reordered = (*reordered[:i], moved, *reordered[i:])
    original = plan

    result = plan.move(moved.id, i)

    assert plan == original
    assert result.day_start == plan.day_start
    assert result.tasks[i].id == moved.id
    assert summary(result) == summary(plan)
    if i == old:
        event("no-op")
        assert result == plan
    elif i > 0 and old > 0:
        event("non-first moves")
        assert result.tasks[:i] == reordered[:i]
        assert_chained(result.tasks[i - 1 :])
    elif old == 0:
        event("first moves down")
        anchor = datetime.combine(plan.tasks[1].slot.start.date(), plan.day_start)
        assert result.tasks[0].slot.start == anchor
        assert_chained(result.tasks)
    else:
        event("to top")
        anchor = datetime.combine(plan.tasks[0].slot.start.date(), plan.day_start)
        assert result.tasks[0].slot.start == anchor
        assert_chained(result.tasks)
