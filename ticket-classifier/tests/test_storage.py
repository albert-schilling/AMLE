import json

import pytest
from pydantic import ValidationError

from ticket_classifier.models import ResolvedTicket
from ticket_classifier.storage import load_tickets, save_results


def test_load_tickets(write_tickets):
    tickets = load_tickets(write_tickets([{"id": "T-1", "text": "x"}]))
    assert [t.id for t in tickets] == ["T-1"]


def test_load_tickets_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(ValidationError):
        load_tickets(path)


def test_save_results_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "results.json"
    save_results(
        [ResolvedTicket(ticket_id="T-1", category="other", priority="low")], path
    )
    assert json.loads(path.read_text()) == [
        {
            "ticket_id": "T-1",
            "customer_id": None,
            "category": "other",
            "priority": "low",
            "escalated": False,
            "escalation_reason": None,
        }
    ]
