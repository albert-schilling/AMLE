import pytest
from conftest import (
    code_result,
    message,
    observation,
    server_tool_use,
    text,
    thinking,
    tool_use,
    web_fetch_result,
)

from ticket_classifier import ClassificationError, TicketClassification, classify
from ticket_classifier.classifier import upload_log
from ticket_classifier.config import get_settings
from ticket_classifier.tools import find_duplicate_charges, lookup_customer

OK = TicketClassification(category="billing", priority="high")


def never(reason):
    return False


@pytest.mark.parametrize(
    ("category", "priority"),
    [("billing", "high"), ("technical", "medium"), ("account", "low")],
)
def test_classify_returns_parsed_classification(
    mock_client, runner_returns, make_ticket, category, priority
):
    expected = TicketClassification(category=category, priority=priority)
    runner_returns([message(parsed_output=expected)])

    result = classify(make_ticket(), mock_client, never)

    assert result.classification == expected
    assert result.escalated is False


def test_classify_configures_tool_runner(
    mock_client, runner_returns, make_ticket, monkeypatch
):
    monkeypatch.setenv("MAX_ITERATIONS", "3")
    runner_returns([message(parsed_output=OK)])

    classify(make_ticket(), mock_client, never)

    kwargs = mock_client.beta.messages.tool_runner.call_args.kwargs
    assert kwargs["tools"][0] is lookup_customer
    assert kwargs["tools"][1].name == "escalate_to_human"
    assert kwargs["tools"][2]["name"] == "web_fetch"
    assert kwargs["tools"][3] is find_duplicate_charges
    assert kwargs["tools"][4]["type"] == "code_execution_20250825"
    assert kwargs["output_format"] is TicketClassification
    assert kwargs["max_iterations"] == 3
    assert kwargs["tool_choice"] == {
        "type": "auto",
        "disable_parallel_tool_use": True,
    }
    assert "Test ticket" in kwargs["messages"][0]["content"]
    assert "1001" in kwargs["messages"][0]["content"]


def test_classify_raises_when_nothing_parsed(mock_client, runner_returns, make_ticket):
    runner_returns([message(stop_reason="max_tokens")])

    with pytest.raises(ClassificationError, match="max_tokens"):
        classify(make_ticket(), mock_client, never)


def test_classify_escalates_automatically_when_cap_is_hit(
    mock_client, runner_returns, make_ticket
):
    runner_returns(
        [
            message(
                tool_use("lookup_customer", customer_id="1001"), stop_reason="tool_use"
            )
        ],
        [observation("{}")],
    )

    result = classify(make_ticket(), mock_client, never)

    assert result.escalated is True
    assert result.classification is None
    assert "Iteration cap" in result.escalation_reason


def test_classify_logs_full_trace(mock_client, runner_returns, make_ticket, caplog):
    runner_returns(
        [
            message(
                text("Need the customer."),
                tool_use("lookup_customer", customer_id="1001"),
                stop_reason="tool_use",
            ),
            message(text('{"category": "billing"}'), parsed_output=OK),
        ],
        [observation("Alice, pro plan"), None],
    )

    caplog.set_level("INFO", logger="ticket_classifier.trace")

    classify(make_ticket(), mock_client, never)

    out = caplog.text
    assert "Thought: Need the customer." in out
    assert "Action: lookup_customer({'customer_id': '1001'})" in out
    assert "Observation: Alice, pro plan" in out
    assert "[T-1] step 1" in out
    assert "step 2 Answer:" in out
    assert "[T-1] Final:" in out


def test_classify_reports_approved_escalation(
    mock_client, runner_returns, make_ticket, mocker
):
    # the real escalation tool is built by classify; simulate the model calling it
    def fake_tool_runner(**kwargs):
        escalate = kwargs["tools"][1]
        escalate.call({"reason": "legal threat"})
        return runner_returns([message(parsed_output=OK)])

    mock_client.beta.messages.tool_runner.side_effect = fake_tool_runner

    result = classify(make_ticket(), mock_client, lambda reason: True)

    assert result.escalated is True
    assert result.escalation_reason == "legal threat"
    assert result.classification == OK


def test_classify_logs_action_before_running_tools(
    mock_client, runner_returns, make_ticket, caplog, mocker
):
    runner = runner_returns(
        [
            message(tool_use("escalate_to_human", reason="x"), stop_reason="tool_use"),
            message(parsed_output=OK),
        ],
        [observation("approved"), None],
    )
    caplog.set_level("INFO", logger="ticket_classifier.trace")
    seen_when_tools_ran = []
    original = runner.generate_tool_call_response

    def spy():
        seen_when_tools_ran.append(caplog.text)
        return original()

    mocker.patch.object(runner, "generate_tool_call_response", side_effect=spy)

    classify(make_ticket(), mock_client, never)

    assert "Action: escalate_to_human" in seen_when_tools_ran[0]
    assert "Observation" not in seen_when_tools_ran[0]


def test_classify_sends_thinking_only_when_budget_set(
    mock_client, runner_returns, make_ticket, monkeypatch
):
    monkeypatch.setenv("THINKING_BUDGET", "0")
    runner_returns([message(parsed_output=OK)])
    classify(make_ticket(), mock_client, never)
    kwargs = mock_client.beta.messages.tool_runner.call_args.kwargs
    assert "thinking" not in kwargs

    monkeypatch.setenv("THINKING_BUDGET", "2000")
    monkeypatch.setenv("MAX_TOKENS", "4000")
    get_settings.cache_clear()
    runner_returns([message(parsed_output=OK)])
    classify(make_ticket(), mock_client, never)
    kwargs = mock_client.beta.messages.tool_runner.call_args.kwargs
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 2000}


def test_classify_logs_thinking_blocks(
    mock_client, runner_returns, make_ticket, caplog
):
    runner_returns(
        [
            message(
                thinking("Customer is angry, check history."),
                tool_use("lookup_customer", customer_id="1001"),
                stop_reason="tool_use",
            ),
            message(parsed_output=OK),
        ],
        [observation("Alice"), None],
    )
    caplog.set_level("INFO", logger="ticket_classifier.trace")

    classify(make_ticket(), mock_client, never)

    assert "step 1 Thinking: Customer is angry, check history." in caplog.text


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (web_fetch_result(url="https://status.mollie.com/x.json"), "web_fetch ok"),
        (web_fetch_result(error_code="url_not_allowed"), "url_not_allowed"),
    ],
)
def test_classify_logs_server_side_web_fetch(
    mock_client, runner_returns, make_ticket, caplog, result, expected
):
    runner_returns(
        [
            message(
                server_tool_use("web_fetch", url="https://status.mollie.com/x.json"),
                result,
                parsed_output=OK,
            )
        ]
    )
    caplog.set_level("INFO", logger="ticket_classifier.trace")

    classify(make_ticket(), mock_client, never)

    assert "Action: web_fetch" in caplog.text
    assert expected in caplog.text


def test_classify_without_log_sends_plain_text(
    mock_client, runner_returns, make_ticket
):
    runner_returns([message(parsed_output=OK)])

    classify(make_ticket(), mock_client, never)

    content = mock_client.beta.messages.tool_runner.call_args.kwargs["messages"][0][
        "content"
    ]
    assert isinstance(content, str)


def test_classify_attaches_log_file_for_the_sandbox(
    mock_client, runner_returns, make_ticket
):
    runner_returns([message(parsed_output=OK)])

    classify(make_ticket(), mock_client, never, log_file_id="file_123")

    content = mock_client.beta.messages.tool_runner.call_args.kwargs["messages"][0][
        "content"
    ]
    assert {"type": "container_upload", "file_id": "file_123"} in content
    assert "Test ticket" in content[0]["text"]


def test_upload_log_returns_the_file_id(mock_client, tmp_path):
    log = tmp_path / "app.log"
    log.write_text("x")
    mock_client.beta.files.upload.return_value.id = "file_9"

    assert upload_log(mock_client, log) == "file_9"
    name, data, _ = mock_client.beta.files.upload.call_args.kwargs["file"]
    assert (name, data) == ("app.log", b"x")


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (code_result(stdout="5\n"), "exit 0: 5"),
        (code_result(error_code="execution_time_exceeded"), "execution_time_exceeded"),
    ],
)
def test_classify_logs_code_execution(
    mock_client, runner_returns, make_ticket, caplog, result, expected
):
    runner_returns(
        [
            message(
                server_tool_use("bash_code_execution", command="grep -c ERROR x"),
                result,
                parsed_output=OK,
            )
        ]
    )
    caplog.set_level("INFO", logger="ticket_classifier.trace")

    classify(make_ticket(), mock_client, never)

    assert "Action: bash_code_execution" in caplog.text
    assert expected in caplog.text
