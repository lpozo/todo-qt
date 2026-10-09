"""Tests for the Qt-free UI message strings."""

from pathlib import Path

from todo_qt.domain import (
    DomainError,
    EmptyTitleError,
    EndNotAfterStartError,
    InvalidTimeSlotError,
)
from todo_qt.services import StoreCorruptError, StoreWriteError
from todo_qt.ui.messages import message_for, save_failure_message, startup_message


def test_empty_title_maps_to_title_required() -> None:
    assert message_for(EmptyTitleError()) == "A title is required."


def test_end_not_after_start_maps_to_end_after_start() -> None:
    assert message_for(EndNotAfterStartError()) == "The end must be after the start."


def test_other_invalid_time_slot_uses_its_own_text() -> None:
    assert message_for(InvalidTimeSlotError("bad slot")) == "bad slot"


def test_other_domain_error_uses_its_text() -> None:
    assert message_for(DomainError("boom")) == "boom"


def test_save_failure_message_includes_reason() -> None:
    error = StoreWriteError(Path("/x/tasks.json"), "disk full")
    assert save_failure_message(error) == (
        "Could not save your changes (disk full). "
        "The change is kept in the list but may be lost if you close the app."
    )


def test_startup_message_includes_path() -> None:
    error = StoreCorruptError(Path("/x/tasks.json"), "bad json")
    assert startup_message(error) == (
        "Your saved tasks could not be read (/x/tasks.json). "
        "Starting with an empty list; the file was left untouched."
    )
