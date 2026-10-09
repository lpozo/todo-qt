"""Shared test helpers: time/id fakes, value builders, and in-memory plan stores."""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Protocol

from todo_qt.domain import Plan, Task, TaskId, TimeSlot
from todo_qt.services import (
    PlanService,
    PlanSnapshot,
    PlanStore,
    StoreCorruptError,
    StoreWriteError,
)

FRI = date(2026, 1, 2)
"""A Friday, the default day for test datetimes."""


def T(hour: int, minute: int = 0, *, day: date = FRI) -> datetime:  # noqa: N802
    """Return a naive, minute-precision datetime on `day`."""
    return datetime.combine(day, time(hour, minute))


class MutableClock:
    """A settable clock returning naive datetimes."""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now if now is not None else T(10, 0)

    def __call__(self) -> datetime:
        return self.now

    def set(self, now: datetime) -> None:
        """Jump to `now`."""
        self.now = now

    def advance(self, delta: timedelta) -> None:
        """Move forward by `delta`."""
        self.now += delta


class IdCounter:
    """Produces unique, predictable task ids: t1, t2, ..."""

    def __init__(self, prefix: str = "t") -> None:
        self._prefix = prefix
        self.count = 0

    def __call__(self) -> TaskId:
        self.count += 1
        return TaskId(f"{self._prefix}{self.count}")


def make_slot(
    start: datetime | None = None,
    end: datetime | None = None,
    *,
    duration: timedelta = timedelta(hours=1),
) -> TimeSlot:
    """Build a valid slot; defaults to 09:00 plus `duration` (or up to `end`)."""
    start = start if start is not None else T(9, 0)
    return TimeSlot(start, end if end is not None else start + duration)


def make_task(
    task_id: str = "t1",
    title: str = "Task",
    slot: TimeSlot | None = None,
    *,
    done: bool = False,
) -> Task:
    """Build a valid task; the default slot is 09:00-10:00 on FRI."""
    return Task(TaskId(task_id), title, slot if slot is not None else make_slot(), done)


def make_plan(*tasks: Task, day_start: time | None = None) -> Plan:
    """Build a plan from tasks; omit `day_start` for the default."""
    if day_start is None:
        return Plan(tasks=tuple(tasks))
    return Plan(tasks=tuple(tasks), day_start=day_start)


class FakeStore:
    """In-memory PlanStore with configurable load and save behavior.

    `plan`: what `load()` returns (None means nothing saved).
    `load_error`: if set, `load()` raises it.
    `save_error`: if set, `save()` records the call and then raises it (every time);
    use `fail_next_save(error)` to fail exactly one save, then succeed again.

    A successful `save()` becomes what `load()` returns next (round trip); a failed
    one leaves the stored plan unchanged.
    """

    def __init__(
        self,
        plan: PlanSnapshot | None = None,
        *,
        load_error: StoreCorruptError | None = None,
        save_error: StoreWriteError | None = None,
    ) -> None:
        self.plan = plan
        self.load_error = load_error
        self.save_error = save_error
        self.load_calls = 0
        self.saves: list[PlanSnapshot] = []
        self._fail_once: StoreWriteError | None = None

    @classmethod
    def corrupt(cls, path: Path = Path("tasks.json"), reason: str = "corrupt") -> FakeStore:
        """A store whose `load()` raises StoreCorruptError."""
        return cls(load_error=StoreCorruptError(path, reason))

    @classmethod
    def failing_saves(
        cls,
        plan: PlanSnapshot | None = None,
        path: Path = Path("tasks.json"),
        reason: str = "disk full",
    ) -> FakeStore:
        """A store whose `save()` raises StoreWriteError."""
        return cls(plan, save_error=StoreWriteError(path, reason))

    def load(self) -> PlanSnapshot | None:
        self.load_calls += 1
        if self.load_error is not None:
            raise self.load_error
        return self.plan

    def save(self, snapshot: PlanSnapshot) -> None:
        self.saves.append(snapshot)
        if self._fail_once is not None:
            error, self._fail_once = self._fail_once, None
            raise error
        if self.save_error is not None:
            raise self.save_error
        self.plan = snapshot

    def fail_next_save(self, error: StoreWriteError) -> None:
        """Make exactly the next `save()` raise `error`; later saves succeed."""
        self._fail_once = error

    @property
    def save_calls(self) -> int:
        """Number of `save` calls so far."""
        return len(self.saves)


class RecordingStore:
    """Wraps another store (default: empty FakeStore), recording every call in order.

    Saves delegate to the inner store, so an inner FakeStore round-trips them.
    `calls` holds ("load", None) and ("save", snapshot) entries. If `error` is set,
    `save()` records and then raises it.
    """

    def __init__(
        self, inner: PlanStore | None = None, *, error: StoreWriteError | None = None
    ) -> None:
        self.inner: PlanStore = inner if inner is not None else FakeStore()
        self.error = error
        self.calls: list[tuple[str, PlanSnapshot | None]] = []

    def load(self) -> PlanSnapshot | None:
        self.calls.append(("load", None))
        return self.inner.load()

    def save(self, snapshot: PlanSnapshot) -> None:
        self.calls.append(("save", snapshot))
        if self.error is not None:
            raise self.error
        self.inner.save(snapshot)

    @property
    def saves(self) -> list[PlanSnapshot]:
        """Snapshots passed to `save`, in order."""
        return [s for kind, s in self.calls if kind == "save" and s is not None]

    @property
    def load_calls(self) -> int:
        """Number of `load` calls so far."""
        return sum(1 for kind, _ in self.calls if kind == "load")


class MakeService(Protocol):
    """Type of the `make_service` fixture."""

    def __call__(self, store: PlanStore | None = None) -> PlanService: ...
