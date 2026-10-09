"""Fixtures built on the shared fakes."""

import pytest

from todo_qt.services import PlanService, PlanStore

from .fakes import FakeStore, IdCounter, MakeService, MutableClock, RecordingStore


@pytest.fixture
def clock() -> MutableClock:
    """A settable clock starting Friday 10:00."""
    return MutableClock()


@pytest.fixture
def new_id() -> IdCounter:
    """Unique ids t1, t2, ..."""
    return IdCounter()


@pytest.fixture
def fake_store() -> FakeStore:
    """An empty in-memory store (load returns None)."""
    return FakeStore()


@pytest.fixture
def recording_store() -> RecordingStore:
    """A store that records every load and save call."""
    return RecordingStore()


@pytest.fixture
def make_service(clock: MutableClock, new_id: IdCounter, fake_store: FakeStore) -> MakeService:
    """Build a PlanService; defaults to the fake_store, clock, and new_id fixtures."""

    def factory(store: PlanStore | None = None) -> PlanService:
        return PlanService(store if store is not None else fake_store, clock, new_id)

    return factory
