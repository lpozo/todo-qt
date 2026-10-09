"""Qt-free user-visible message strings."""

from todo_qt.domain import (
    DomainError,
    EmptyTitleError,
    EndNotAfterStartError,
)
from todo_qt.services import StoreCorruptError, StoreWriteError

TITLE_REQUIRED = "A title is required."
END_AFTER_START = "The end must be after the start."


def message_for(error: DomainError) -> str:
    """Return the user-facing message for a domain error."""
    if isinstance(error, EmptyTitleError):
        return TITLE_REQUIRED
    if isinstance(error, EndNotAfterStartError):
        return END_AFTER_START
    return str(error)


def save_failure_message(error: StoreWriteError) -> str:
    """Return the message shown when saving fails."""
    return (
        f"Could not save your changes ({error.reason}). "
        "The change is kept in the list but may be lost if you close the app."
    )


def startup_message(error: StoreCorruptError) -> str:
    """Return the message shown when saved data is unreadable."""
    return (
        f"Your saved tasks could not be read ({error.path}). "
        "Starting with an empty list; the file was left untouched."
    )
