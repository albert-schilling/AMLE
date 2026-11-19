"""The commands end to end: real graph and SQLite file, only the model is mocked."""

import json

import pytest
from helpers import HIGH

from ticket_classifier import commands
from ticket_classifier.config import get_settings


@pytest.fixture
def settings(monkeypatch, tmp_path, results_file):
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "out" / "checkpoints.db"))
    monkeypatch.setenv("GRAPH_PATH", str(tmp_path / "out" / "graph.mmd"))
    monkeypatch.setenv("TRACE_FILE", str(tmp_path / "out" / "trace.jsonl"))
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def triage(model):
    model.outcomes["urgent"] = HIGH
    return model


def tickets(make_ticket):
    return [make_ticket(id="T-1", text="urgent"), make_ticket(id="T-2", text="hi")]


def saved_results(settings):
    return {r["ticket_id"]: r for r in json.loads(settings.results_path.read_text())}


def test_run_saves_handled_tickets_and_pauses_high_priority(
    settings, triage, make_ticket
):
    batch = commands.run(tickets(make_ticket), settings)

    assert batch.paused == ["T-1"]
    assert list(saved_results(settings)) == ["T-2"]
    assert settings.graph_path.exists()
    trace = [json.loads(line) for line in settings.trace_file.read_text().splitlines()]
    events = {(r["ticket_id"], r["node"], r["event"]) for r in trace}
    assert ("T-1", "human_review", "paused") in events
    assert ("T-2", "__end__", "finished") in events


def test_resume_finishes_paused_ticket_and_keeps_others(settings, triage, make_ticket):
    commands.run(tickets(make_ticket), settings)

    classified = commands.resume(
        "T-1", {"approved": True, "note": "Dana takes it"}, settings
    )

    assert classified.escalation_reason == "Dana takes it"
    results = saved_results(settings)
    assert list(results) == ["T-2", "T-1"]
    assert results["T-1"]["escalated"] is True
    assert triage.call_count == 2  # one per ticket, none on resume


def test_resume_works_without_api_key(settings, triage, make_ticket, monkeypatch):
    commands.run(tickets(make_ticket), settings)
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    classified = commands.resume("T-1", {"approved": False, "note": ""}, settings)

    assert classified.escalated is False


def test_run_without_api_key_raises_before_any_work(
    settings, triage, make_ticket, monkeypatch
):
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    with pytest.raises(commands.MissingApiKeyError):
        commands.run(tickets(make_ticket), settings)
    triage.assert_not_called()
    assert not settings.checkpoint_path.exists()
