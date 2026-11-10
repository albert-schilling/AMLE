import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ticket_classifier import (
    ClassificationError,
    Ticket,
    TicketClassification,
    classify,
)
from ticket_classifier.classifier import create_prompt
from ticket_classifier.cli import main
from ticket_classifier.config import Settings
from ticket_classifier.tools import lookup_customer

CUSTOMERS = {
    "1001": {
        "id": "1001",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        "account_age_days": 430,
        "past_refunds_90d": 2,
        "plan": "pro",
        "products": ["Wendel", "Pip"],
    }
}


def ticket(customer_id="1001", text="Test ticket"):
    return Ticket(id="T-1", customer_id=customer_id, text=text)


def runner_returns(mock_client, parsed_output, stop_reason="end_turn"):
    """Make the fake client's tool runner finish with the given parsed output."""
    final = SimpleNamespace(parsed_output=parsed_output, stop_reason=stop_reason)
    mock_client.beta.messages.tool_runner.return_value.until_done.return_value = final


@pytest.fixture
def customers_file(monkeypatch, tmp_path):
    path = tmp_path / "customers.json"
    path.write_text(json.dumps(CUSTOMERS))
    monkeypatch.setenv("CUSTOMERS_PATH", str(path))
    return path


@pytest.fixture
def results_file(monkeypatch, tmp_path):
    path = tmp_path / "out" / "results.json"
    monkeypatch.setenv("RESULTS_PATH", str(path))
    return path


def write_tickets(tmp_path, tickets):
    path = tmp_path / "tickets.json"
    path.write_text(json.dumps(tickets))
    return path


# --- classify -------------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "priority"),
    [("billing", "high"), ("technical", "medium"), ("account", "low")],
)
def test_classify_returns_parsed_classification(mock_client, category, priority):
    expected = TicketClassification(category=category, priority=priority)
    runner_returns(mock_client, expected)

    assert classify(ticket(), client=mock_client) == expected


def test_classify_configures_tool_runner(mock_client):
    runner_returns(mock_client, TicketClassification(category="other", priority="low"))

    classify(ticket(), client=mock_client)

    mock_client.beta.messages.tool_runner.assert_called_once()
    kwargs = mock_client.beta.messages.tool_runner.call_args.kwargs
    assert kwargs["tools"] == [lookup_customer]
    assert kwargs["output_format"] is TicketClassification
    assert "Test ticket" in kwargs["messages"][0]["content"]
    assert "1001" in kwargs["messages"][0]["content"]


def test_classify_raises_when_nothing_parsed(mock_client):
    runner_returns(mock_client, None, stop_reason="max_tokens")

    with pytest.raises(ClassificationError, match="max_tokens"):
        classify(ticket(), client=mock_client)


# --- prompt ---------------------------------------------------------------


def test_prompt_includes_customer_id():
    assert "Customer ID: 1001" in create_prompt(ticket("1001"))


def test_prompt_without_customer_id():
    prompt = create_prompt(ticket(customer_id=None))
    assert "Customer ID" not in prompt
    assert "Test ticket" in prompt


# --- lookup_customer ------------------------------------------------------


def test_lookup_customer_found(customers_file):
    result = json.loads(lookup_customer.call({"customer_id": "1001"}))

    assert result["first_name"] == "Alice"
    assert result["products"] == ["Wendel", "Pip"]
    assert result["past_refunds_90d"] == 2


def test_lookup_customer_not_found(customers_file):
    assert lookup_customer.call({"customer_id": "9999"}) == "Customer not found"


# --- models and settings --------------------------------------------------


def test_classification_rejects_unknown_category():
    with pytest.raises(ValidationError):
        TicketClassification(category="spam", priority="low")


def test_ticket_customer_id_is_optional():
    assert Ticket(id="T-1", text="x").customer_id is None


def test_settings_require_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_invalid_log_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings()


# --- CLI ------------------------------------------------------------------


def test_main_writes_results(mocker, tmp_path, results_file):
    tickets = write_tickets(
        tmp_path,
        [
            {"id": "T-1", "customer_id": "1001", "text": "Charged twice"},
            {"id": "T-2", "text": "No customer id"},
        ],
    )
    mocker.patch("ticket_classifier.cli.create_client")
    mocker.patch(
        "ticket_classifier.cli.classify",
        return_value=TicketClassification(category="billing", priority="high"),
    )

    assert main([str(tickets)]) == 0
    assert json.loads(results_file.read_text()) == [
        {
            "ticket_id": "T-1",
            "customer_id": "1001",
            "category": "billing",
            "priority": "high",
        },
        {
            "ticket_id": "T-2",
            "customer_id": None,
            "category": "billing",
            "priority": "high",
        },
    ]


def test_main_overwrites_previous_results(mocker, tmp_path, results_file):
    results_file.parent.mkdir()
    results_file.write_text('[{"stale": true}]')
    tickets = write_tickets(tmp_path, [{"id": "T-1", "text": "x"}])
    mocker.patch("ticket_classifier.cli.create_client")
    mocker.patch(
        "ticket_classifier.cli.classify",
        return_value=TicketClassification(category="other", priority="low"),
    )

    main([str(tickets)])

    assert [r["ticket_id"] for r in json.loads(results_file.read_text())] == ["T-1"]


def test_main_returns_nonzero_on_failure(mocker, tmp_path, results_file):
    tickets = write_tickets(
        tmp_path, [{"id": "T-1", "text": "bad"}, {"id": "T-2", "text": "good"}]
    )
    mocker.patch("ticket_classifier.cli.create_client")
    mocker.patch(
        "ticket_classifier.cli.classify",
        side_effect=[
            ClassificationError("boom"),
            TicketClassification(category="other", priority="low"),
        ],
    )

    assert main([str(tickets)]) == 1
    # the failed ticket is skipped, the other one is still saved
    assert [r["ticket_id"] for r in json.loads(results_file.read_text())] == ["T-2"]


def test_main_uses_tickets_path_setting(mocker, tmp_path, monkeypatch, results_file):
    tickets = write_tickets(tmp_path, [{"id": "T-1", "text": "x"}])
    monkeypatch.setenv("TICKETS_PATH", str(tickets))
    mocker.patch("ticket_classifier.cli.create_client")
    classify_mock = mocker.patch(
        "ticket_classifier.cli.classify",
        return_value=TicketClassification(category="other", priority="low"),
    )

    assert main([]) == 0
    classify_mock.assert_called_once()
