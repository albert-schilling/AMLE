import json

import pytest
from helpers import REPLY, REPLY_TEXT
from pydantic import ValidationError

from ticket_classifier.models import ResolvedTicket
from ticket_classifier.storage import load_tickets, merge_results, save_results


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
        [
            ResolvedTicket(
                ticket_id="T-1", category="other", priority="low", reply=REPLY
            )
        ],
        path,
    )
    assert json.loads(path.read_text()) == [
        {
            "ticket_id": "T-1",
            "customer_id": None,
            "category": "other",
            "priority": "low",
            "reply": {"text": REPLY_TEXT, "citations": []},
            "escalated": False,
            "escalation_reason": None,
        }
    ]


def test_merge_results_replaces_same_id_and_keeps_others(tmp_path):
    path = tmp_path / "results.json"
    save_results(
        [
            ResolvedTicket(
                ticket_id="T-1", category="other", priority="low", reply=REPLY
            ),
            ResolvedTicket(
                ticket_id="T-2", category="other", priority="low", reply=REPLY
            ),
        ],
        path,
    )

    merge_results(
        [
            ResolvedTicket(
                ticket_id="T-2", category="billing", priority="high", reply=REPLY
            )
        ],
        path,
    )

    saved = json.loads(path.read_text())
    assert [(r["ticket_id"], r["category"]) for r in saved] == [
        ("T-1", "other"),
        ("T-2", "billing"),
    ]


def test_merge_results_without_saved_file(tmp_path):
    path = tmp_path / "results.json"

    merge_results(
        [
            ResolvedTicket(
                ticket_id="T-1", category="other", priority="low", reply=REPLY
            )
        ],
        path,
    )

    assert [r["ticket_id"] for r in json.loads(path.read_text())] == ["T-1"]
