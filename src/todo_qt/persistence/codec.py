"""JSON (de)serialization of a plan (internal to the persistence layer)."""

import json
from datetime import datetime, time
from typing import Any

from todo_qt.domain import Plan, Task, TaskId, TimeSlot

SCHEMA_VERSION = 1

_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
_TIME_FORMAT = "%H:%M"


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
    """Return the plan stored in a JSON document (strict validation comes later)."""
    document: dict[str, Any] = json.loads(text)
    tasks = tuple(
        Task(
            TaskId(record["id"]),
            record["title"],
            TimeSlot(
                datetime.strptime(record["start"], _DATETIME_FORMAT),
                datetime.strptime(record["end"], _DATETIME_FORMAT),
            ),
            record["done"],
        )
        for record in document["tasks"]
    )
    day_start = datetime.strptime(document["day_start"], _TIME_FORMAT).time()
    return Plan(tasks, time(day_start.hour, day_start.minute))
