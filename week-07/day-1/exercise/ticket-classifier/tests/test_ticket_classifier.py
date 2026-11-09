import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ticket_classifier import ClassificationError, TicketClassification, classify
from ticket_classifier.cli import main
from ticket_classifier.config import Settings


def tool_response(args):
    block = SimpleNamespace(type="tool_use", name="classify_ticket", input=args)
    return SimpleNamespace(content=[block], stop_reason="tool_use")


@pytest.mark.parametrize(
    ("category", "priority"),
    [("billing", "high"), ("technical", "medium"), ("account", "low")],
)
def test_classify_returns_parsed_classification(mock_client, category, priority):
    expected = TicketClassification(category=category, priority=priority)
    mock_client.messages.create.return_value = tool_response(
        {"category": category, "priority": priority}
    )

    assert classify("Test ticket", client=mock_client) == expected


def test_classify_sends_ticket_to_model(mock_client):
    mock_client.messages.create.return_value = tool_response(
        {"category": "other", "priority": "low"}
    )

    classify("Test ticket", client=mock_client)

    mock_client.messages.create.assert_called_once()
    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["tools"][0]["name"] == "classify_ticket"
    assert "Test ticket" in kwargs["messages"][0]["content"]


def test_classify_raises_when_no_tool_call(mock_client):
    mock_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="hi")], stop_reason="end_turn"
    )

    with pytest.raises(ClassificationError):
        classify("Test ticket", client=mock_client)


def test_classify_raises_on_invalid_tool_args(mock_client):
    mock_client.messages.create.return_value = tool_response(
        {"category": "spam", "priority": "low"}
    )

    with pytest.raises(ClassificationError):
        classify("Test ticket", client=mock_client)


def test_classification_rejects_unknown_category():
    with pytest.raises(ValidationError):
        TicketClassification(category="spam", priority="low")


def test_settings_require_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ValidationError):
        Settings()


def test_main_classifies_tickets_from_file(mocker, tmp_path, capsys):
    tickets = tmp_path / "tickets.json"
    tickets.write_text(json.dumps([{"id": "T-1", "text": "Charged twice"}]))
    mocker.patch("ticket_classifier.cli.create_client")
    mocker.patch(
        "ticket_classifier.cli.classify",
        return_value=TicketClassification(category="billing", priority="high"),
    )

    assert main([str(tickets)]) == 0
    assert "T-1: Charged twice -> billing high" in capsys.readouterr().out


def test_main_returns_nonzero_on_failure(mocker, tmp_path):
    tickets = tmp_path / "tickets.json"
    tickets.write_text(json.dumps([{"id": "T-1", "text": "x"}]))
    mocker.patch("ticket_classifier.cli.create_client")
    mocker.patch(
        "ticket_classifier.cli.classify", side_effect=ClassificationError("boom")
    )

    assert main([str(tickets)]) == 1
