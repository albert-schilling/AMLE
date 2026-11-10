from types import SimpleNamespace

import pytest

from ticket_classifier import ClassificationError, TicketClassification, classify
from ticket_classifier.tools import lookup_customer


def runner_returns(mock_client, parsed_output, stop_reason="end_turn"):
    """Make the fake client's tool runner finish with the given parsed output."""
    final = SimpleNamespace(parsed_output=parsed_output, stop_reason=stop_reason)
    mock_client.beta.messages.tool_runner.return_value.until_done.return_value = final


@pytest.mark.parametrize(
    ("category", "priority"),
    [("billing", "high"), ("technical", "medium"), ("account", "low")],
)
def test_classify_returns_parsed_classification(
    mock_client, make_ticket, category, priority
):
    expected = TicketClassification(category=category, priority=priority)
    runner_returns(mock_client, expected)

    assert classify(make_ticket(), mock_client) == expected


def test_classify_configures_tool_runner(mock_client, make_ticket, monkeypatch):
    monkeypatch.setenv("MAX_ITERATIONS", "3")
    runner_returns(mock_client, TicketClassification(category="other", priority="low"))

    classify(make_ticket(), mock_client)

    mock_client.beta.messages.tool_runner.assert_called_once()
    kwargs = mock_client.beta.messages.tool_runner.call_args.kwargs
    assert kwargs["tools"] == [lookup_customer]
    assert kwargs["output_format"] is TicketClassification
    assert kwargs["max_iterations"] == 3
    assert "Test ticket" in kwargs["messages"][0]["content"]
    assert "1001" in kwargs["messages"][0]["content"]


def test_classify_raises_when_nothing_parsed(mock_client, make_ticket):
    runner_returns(mock_client, None, stop_reason="max_tokens")

    with pytest.raises(ClassificationError, match="max_tokens"):
        classify(make_ticket(), mock_client)
