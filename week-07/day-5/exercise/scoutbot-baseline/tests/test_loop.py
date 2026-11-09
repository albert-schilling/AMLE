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


def _server_tool_use_block(name, input_, tool_use_id="srvtoolu_1"):
    return SimpleNamespace(type="server_tool_use", name=name, input=input_, id=tool_use_id)


def _web_fetch_result_block(tool_use_id, url, content_text):
    return SimpleNamespace(
        type="web_fetch_tool_result",
        tool_use_id=tool_use_id,
        content=SimpleNamespace(
            type="web_fetch_result",
            url=url,
            content=SimpleNamespace(source=SimpleNamespace(data=content_text)),
        ),
    )


def _bash_result_block(tool_use_id, stdout, return_code=0):
    return SimpleNamespace(
        type="bash_code_execution_tool_result",
        tool_use_id=tool_use_id,
        content=SimpleNamespace(
            type="bash_code_execution_result", stdout=stdout, stderr="", return_code=return_code
        ),
    )


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


@patch("scoutbot.loop._client")
def test_loop_records_web_fetch_as_a_step_without_a_second_turn(mock_client):
    """A server tool's result is already baked into the *same* response - unlike a client
    tool, the loop must not treat it as "needs another turn"."""
    tool_use_id = "srvtoolu_1"
    mock_client.return_value.messages.create.return_value = _response(
        _text_block("Checking Stripe's status before refunding."),
        _server_tool_use_block("web_fetch", {"url": "https://status.stripe.com"}, tool_use_id),
        _web_fetch_result_block(tool_use_id, "https://status.stripe.com", "All systems operational."),
        _text_block("Stripe reports no outage, so this charge isn't on their end."),
    )

    result = run_agent_loop("Was I double-charged because of an outage?", customer_id="1001")

    assert mock_client.return_value.messages.create.call_count == 1
    assert len(result.steps) == 2
    assert result.steps[0].action == "web_fetch"
    assert result.steps[0].observation["url"] == "https://status.stripe.com"
    assert "All systems operational" in result.steps[0].observation["content_preview"]
    assert result.steps[1].action is None
    assert "no outage" in result.final_answer


@patch("scoutbot.loop._client")
def test_loop_records_code_execution_result(mock_client):
    tool_use_id = "srvtoolu_2"
    mock_client.return_value.messages.create.return_value = _response(
        _text_block("Running a count against the log."),
        _server_tool_use_block("bash_code_execution", {"command": "grep ERROR log.txt | wc -l"}, tool_use_id),
        _bash_result_block(tool_use_id, stdout="5\n"),
        _text_block("5 errors happened at or after 3pm."),
    )

    result = run_agent_loop("How many errors after 3pm?", customer_id="1002")

    assert result.steps[0].action == "bash_code_execution"
    assert result.steps[0].observation["stdout"] == "5\n"
    assert result.steps[0].observation["return_code"] == 0
    assert "5 errors" in result.final_answer


@patch("scoutbot.loop._client")
def test_loop_still_continues_when_a_client_tool_follows_a_server_tool(mock_client):
    """A server tool call doesn't block a *later* client tool call from starting a normal
    next turn - the loop should still recognize and execute it."""
    tool_use_id = "srvtoolu_3"
    mock_client.return_value.messages.create.side_effect = [
        _response(
            _text_block("Checking Stripe first."),
            _server_tool_use_block("web_fetch", {"url": "https://status.stripe.com"}, tool_use_id),
            _web_fetch_result_block(tool_use_id, "https://status.stripe.com", "All systems operational."),
            _text_block("No outage - escalating for a human refund decision."),
            _tool_use_block("escalate_to_human", {"reason": "duplicate charge, no known cause"}),
        ),
        _response(_text_block("Escalated.")),
    ]

    result = run_agent_loop(
        "I was double-charged, is it Stripe's fault?", customer_id="1001", approve_fn=lambda r: True
    )

    assert len(result.steps) == 3  # web_fetch step, escalate_to_human step, final answer step
    assert result.steps[0].action == "web_fetch"
    assert result.steps[1].action == "escalate_to_human"
    assert result.steps[1].observation["approved"] is True
    assert result.final_answer == "Escalated."
