"""Errors raised by plan stores."""

from pathlib import Path


class StoreError(Exception):
    """Base class for plan store failures."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(path, reason)
        self.path = path
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


class StoreCorruptError(StoreError):
    """Saved data exists but cannot be loaded."""


class StoreWriteError(StoreError):
    """The plan could not be persisted."""
