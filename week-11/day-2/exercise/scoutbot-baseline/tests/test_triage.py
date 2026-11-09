"""These tests patch the Anthropic SDK boundary directly (`scoutbot.core._client`), so they
run offline - no real API key or network access needed. The production code stays
simple/direct (no injected client abstraction); only the test reaches in and replaces the
boundary.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scoutbot.core import TriageError, triage


def _fake_response(input_dict: dict):
    """Mimics an Anthropic Message response containing a single tool_use content block.

    Unlike OpenAI's function-call arguments (a JSON string), Anthropic's tool_use block
    exposes `.input` already parsed into a dict.
    """
    tool_use_block = SimpleNamespace(type="tool_use", name="triage_ticket", input=input_dict)
    return SimpleNamespace(content=[tool_use_block])


@patch("scoutbot.core._client")
def test_triage_returns_validated_result(mock_client):
    mock_client.return_value.messages.create.return_value = _fake_response(
        {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}
    )

    result = triage("I was charged twice, please refund me.")

    assert result.category == "billing"
    assert result.priority == "high"
    assert result.suggested_owner == "billing-team"
    mock_client.return_value.messages.create.assert_called_once()


@patch("scoutbot.core._client")
def test_triage_retries_once_then_raises_on_repeated_bad_data(mock_client):
    mock_client.return_value.messages.create.return_value = _fake_response(
        {"category": "billing", "priority": "urgent!!", "suggested_owner": "billing-team"}
    )

    with pytest.raises(TriageError):
        triage("this will fail schema validation twice")

    assert mock_client.return_value.messages.create.call_count == 2


@patch("scoutbot.core._client")
def test_triage_succeeds_on_second_attempt(mock_client):
    bad = _fake_response({"category": "billing", "priority": "urgent!!", "suggested_owner": "x"})
    good = _fake_response({"category": "billing", "priority": "high", "suggested_owner": "billing-team"})
    mock_client.return_value.messages.create.side_effect = [bad, good]

    result = triage("flaky first reply, valid second reply")

    assert result.priority == "high"
    assert mock_client.return_value.messages.create.call_count == 2


@patch("scoutbot.core._client")
def test_triage_raises_when_model_never_calls_the_tool(mock_client):
    no_tool_call_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="I'd rather not classify this one.")]
    )
    mock_client.return_value.messages.create.return_value = no_tool_call_response

    with pytest.raises(TriageError):
        triage("model ignores the tool entirely")
