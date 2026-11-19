import json

import pytest

from ticket_classifier.config import get_settings
from ticket_classifier.models import Ticket
from ticket_classifier.trace import trace_event


@pytest.fixture
def trace_file(monkeypatch, tmp_path):
    path = tmp_path / "out" / "trace.jsonl"
    monkeypatch.setenv("TRACE_FILE", str(path))
    get_settings.cache_clear()
    return path


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_one_line_per_event_with_ticket_id(trace_file):
    trace_event("T-1", "triage", "updated", {"x": 1})
    trace_event("T-2", "triage", "updated", {"x": 2})

    first, second = records(trace_file)
    assert {k: first[k] for k in ("ticket_id", "node", "event", "data")} == {
        "ticket_id": "T-1",
        "node": "triage",
        "event": "updated",
        "data": {"x": 1},
    }
    assert second["ticket_id"] == "T-2"
    assert "timestamp" in first


def test_models_are_written_as_json_objects(trace_file):
    trace_event(
        "T-1", "get_customer", "updated", {"ticket": Ticket(id="T-1", text="x")}
    )

    (record,) = records(trace_file)
    assert record["data"]["ticket"] == {"id": "T-1", "customer_id": None, "text": "x"}
