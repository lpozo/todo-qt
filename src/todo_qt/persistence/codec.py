"""JSON (de)serialization of a plan (internal to the persistence layer)."""

import json
from datetime import datetime

from todo_qt.domain import DomainError, Plan, Task, TaskId, TimeSlot

SCHEMA_VERSION = 1

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
_TIME_FORMAT = "%H:%M"


class CodecError(ValueError):
    """The document is not a valid saved plan."""


def encode(plan: Plan) -> str:
    """Return the plan as a JSON document."""
    document = {
        "schema_version": SCHEMA_VERSION,
        "day_start": plan.day_start.strftime(_TIME_FORMAT),
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "start": task.slot.start.strftime(_DATETIME_FORMAT),
                "end": task.slot.end.strftime(_DATETIME_FORMAT),
                "done": task.done,
            }
            for task in plan.tasks
        ],
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def decode(text: str) -> Plan:
    """Return the plan stored in a JSON document, raising CodecError if it is invalid."""
    try:
        document = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise CodecError(f"not valid JSON: {error}") from error
    document = _expect(document, dict, "document")
    version = document.get("schema_version")
    if type(version) is not int:
        raise CodecError("schema_version must be an integer")
    if version != SCHEMA_VERSION:
        raise CodecError(f"unsupported schema_version {version} (expected {SCHEMA_VERSION})")
    records = _expect(document.get("tasks"), list, "tasks")
    try:
        tasks = tuple(_decode_task(record) for record in records)
        day_start = _parse(_expect(document.get("day_start"), str, "day_start"), _TIME_FORMAT)
        return Plan(tasks, day_start.time())
    except DomainError as error:
        raise CodecError(f"invalid plan: {error}") from error


def _decode_task(record: object) -> Task:
    """Build a task from one JSON object."""
    fields = _expect(record, dict, "task")
    start = _parse(_expect(fields.get("start"), str, "task start"), _DATETIME_FORMAT)
    end = _parse(_expect(fields.get("end"), str, "task end"), _DATETIME_FORMAT)
    return Task(
        TaskId(_expect(fields.get("id"), str, "task id")),
        _expect(fields.get("title"), str, "task title"),
        TimeSlot(start, end),
        _expect(fields.get("done"), bool, "task done"),
    )


def _expect[V](value: object, kind: type[V], name: str) -> V:
    """Return `value` if it is exactly of type `kind`, else raise CodecError."""
    if type(value) is not kind:
        raise CodecError(f"{name} must be of type {kind.__name__}")
    return value


def _parse(value: str, fmt: str) -> datetime:
    """Parse `value` strictly with `fmt`."""
    try:
        parsed = datetime.strptime(value, fmt)
    except ValueError as error:
        raise CodecError(f"{value!r} does not match {fmt}") from error
    if parsed.strftime(fmt) != value:
        raise CodecError(f"{value!r} is not in the canonical form {fmt}")
    return parsed
