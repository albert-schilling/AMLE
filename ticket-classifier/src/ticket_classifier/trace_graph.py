"""Trace actions within the ticket classifier workflow and log them as JSON lines."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ticket_classifier.config import get_settings

from .models import TriageState

TRACE_LOGGER_NAME = "ticket_classifier.graph_trace"
trace_logger = logging.getLogger(TRACE_LOGGER_NAME)


def log_action(node: str, action: str, state: TriageState) -> None:
    settings = get_settings()

    record = {
        "node": node,
        "action": action,
        "timestamp": datetime.now(UTC).isoformat(),
        # "state": TypeAdapter(TriageState).dump_python(state),
        **state,
    }

    append_jsonl(settings.trace_file, record)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one record as a single JSON line (JSON Lines)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, default=str) + "\n")
