"""Conversions between Qt date-time values and naive Python datetimes."""

from datetime import datetime

from PySide6.QtCore import QDateTime


def to_qdatetime(value: datetime) -> QDateTime:
    """Convert a naive datetime to a minute-precision QDateTime."""
    return QDateTime(value.year, value.month, value.day, value.hour, value.minute, 0)


def to_datetime(value: QDateTime) -> datetime:
    """Convert a QDateTime to a naive datetime with seconds and ms zeroed."""
    date, time = value.date(), value.time()
    return datetime(date.year(), date.month(), date.day(), time.hour(), time.minute())
