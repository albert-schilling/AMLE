"""These tests patch the Anthropic SDK boundary directly (`scoutbot.loop._client`), so they
run offline - no real API key or network access needed, same pattern as Day 1's
tests/test_triage.py.
"""
from types import SimpleNamespace
from unittest.mock import patch

from scoutbot.loop import run_agent_loop


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(name, input_, tool_use_id="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=tool_use_id)


def _response(*blocks):
    return SimpleNamespace(content=list(blocks))


@patch("scoutbot.loop._client")
def test_loop_looks_up_then_answers(mock_client):
    mock_client.return_value.messages.create.side_effect = [
        _response(
            _text_block("I should check the account first."),
            _tool_use_block("look_up_customer", {"customer_id": "1001"}),
        ),
        _response(_text_block("Final answer: pro customer, no need to escalate.")),
    ]

    result = run_agent_loop("Some billing ticket", customer_id="1001")

    assert result.final_answer == "Final answer: pro customer, no need to escalate."
    assert result.escalated is False
    assert len(result.steps) == 2
    assert result.steps[0].action == "look_up_customer"
    assert result.steps[0].observation == {
        "found": True,
        "customer_id": "1001",
        "plan": "pro",
        "account_age_days": 430,
        "past_refunds_90d": 2,
    }
    assert result.steps[1].action is None


@patch("scoutbot.loop._client")
def test_loop_hits_step_cap_and_escalates(mock_client):
    # Always returns a tool call, never a final answer - loop must stop on its own.
    mock_client.return_value.messages.create.return_value = _response(
        _text_block("Still thinking..."),
        _tool_use_block("look_up_customer", {"customer_id": "1001"}),
    )

    result = run_agent_loop("An unresolvable ticket", customer_id="1001", max_steps=3)

    assert result.escalated is True
    assert "step limit" in result.final_answer
    assert len(result.steps) == 4  # 3 tool-use steps + 1 cap-hit step
    assert mock_client.return_value.messages.create.call_count == 3


@patch("scoutbot.loop._client")
def test_loop_escalation_requires_approval(mock_client):
    mock_client.return_value.messages.create.side_effect = [
        _response(
            _text_block("This needs a human."),
            _tool_use_block("escalate_to_human", {"reason": "needs a refund decision"}),
        ),
        _response(_text_block("Escalation was rejected; here's a draft reply instead.")),
    ]

    result = run_agent_loop(
        "A tricky refund request", customer_id="1001", approve_fn=lambda reason: False
    )

    assert result.steps[0].action == "escalate_to_human"
    assert result.steps[0].observation == {
        "approved": False,
        "note": "Escalation rejected by human reviewer.",
    }
    assert result.final_answer == "Escalation was rejected; here's a draft reply instead."


@patch("scoutbot.loop._client")
def test_loop_only_executes_first_tool_use_per_turn(mock_client):
    mock_client.return_value.messages.create.side_effect = [
        _response(
            _text_block("Doing two things at once."),
            _tool_use_block("look_up_customer", {"customer_id": "1001"}, tool_use_id="toolu_a"),
            _tool_use_block("escalate_to_human", {"reason": "just in case"}, tool_use_id="toolu_b"),
        ),
        _response(_text_block("Done.")),
    ]

    result = run_agent_loop("Ambiguous ticket", customer_id="1001")

    assert len(result.steps) == 2
    assert result.steps[0].action == "look_up_customer"
