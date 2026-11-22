"""JSON lines trace: one record per workflow event, for later analysis.

Records hold ticket, customer and reviewer text, so this file is never exported.
"""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic_core import to_jsonable_python

from .config import get_settings


def trace_event(ticket_id: str, node: str, event: str, data: Any) -> None:
    """Append one event of a ticket's run to ``TRACE_FILE``.

    Models in ``data`` are written as JSON objects, not as Python reprs.
    """
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "ticket_id": ticket_id,
        "node": node,
        "event": event,
        "data": data,
    }
    path = get_settings().trace_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(to_jsonable_python(record)) + "\n")
