import json

from ticket_classifier.tools import (
    Escalation,
    find_duplicate_charges,
    lookup_customer,
    make_code_execution_tool,
    make_escalation_tool,
    make_fetch_tool,
    make_web_fetch_tool,
)


def test_lookup_customer_found(customers_file):
    result = json.loads(lookup_customer.call({"customer_id": "1001"}))

    assert result["first_name"] == "Alice"
    assert result["products"] == ["Wendel", "Pip"]
    assert result["past_refunds_90d"] == 2


def test_lookup_customer_not_found(customers_file):
    assert lookup_customer.call({"customer_id": "9999"}) == "Customer not found"


def test_lookup_customer_malformed_record(customers_file):
    customers_file.write_text(json.dumps({"1001": {"id": "1001"}}))

    assert (
        lookup_customer.call({"customer_id": "1001"}) == "Customer record unavailable"
    )


def test_escalation_needs_approval_before_it_counts():
    escalation = Escalation(lambda reason: True)
    tool = make_escalation_tool(escalation)

    result = tool.call({"reason": "legal threat"})

    assert escalation.reason == "legal threat"
    assert "approved" in result


def test_rejected_escalation_is_an_observation_not_an_effect():
    escalation = Escalation(lambda reason: False)
    tool = make_escalation_tool(escalation)

    result = tool.call({"reason": "legal threat"})

    assert escalation.reason is None
    assert "rejected" in result


def test_second_escalation_does_not_ask_the_human_again():
    asked = []

    def approve(reason):
        asked.append(reason)
        return True

    escalation = Escalation(approve)
    tool = make_escalation_tool(escalation)

    tool.call({"reason": "first"})
    result = tool.call({"reason": "second"})

    assert asked == ["first"]
    assert escalation.reason == "first"
    assert "Already escalated" in result


def test_web_fetch_tool_has_guardrails():
    tool = make_web_fetch_tool()

    assert tool["type"] == "web_fetch_20250910"
    assert tool["max_uses"] == 3
    assert tool["allowed_domains"] == [
        "status.mollie.com",
        "albert-schilling.github.io",
    ]
    assert tool["max_content_tokens"] > 0


def test_web_fetch_guardrails_follow_settings(monkeypatch):
    monkeypatch.setenv("STATUS_DOMAIN", "status.example.com")
    monkeypatch.setenv("WEB_FETCH_MAX_USES", "1")

    tool = make_web_fetch_tool()

    assert tool["allowed_domains"][0] == "status.example.com"
    assert tool["max_uses"] == 1


def row(client_id, invoice, amount, timestamp):
    return {
        "client_id": client_id,
        "invoice_number": invoice,
        "amount": amount,
        "timestamp": timestamp,
    }


def test_find_duplicate_charges_reports_pair():
    rows = [
        row("1001", "A", 29.0, "2026-11-03T08:15:00Z"),
        row("1001", "B", 29.0, "2026-11-03T08:15:41Z"),
    ]

    result = json.loads(
        find_duplicate_charges.call({"client_id": "1001", "payments": rows})
    )

    assert result == [{"invoices": ["A", "B"], "amount": "29.0", "seconds_apart": 41}]


def test_find_duplicate_charges_ignores_other_clients_and_amounts():
    rows = [
        row("1001", "A", 29.0, "2026-11-03T08:15:00Z"),
        row("1002", "B", 29.0, "2026-11-03T08:15:41Z"),  # other client
        row("1001", "C", 14.5, "2026-11-03T08:16:00Z"),  # other amount
        row("1001", "D", 29.0, "2026-12-03T08:15:00Z"),  # a month later
    ]

    result = find_duplicate_charges.call({"client_id": "1001", "payments": rows})

    assert result == "No duplicate charges found for client 1001"


def test_find_duplicate_charges_rejects_malformed_rows():
    result = find_duplicate_charges.call(
        {"client_id": "1001", "payments": [{"client_id": "1001"}]}
    )

    assert result.startswith("Invalid payment rows")


def test_fetch_backend_server_is_default():
    assert make_fetch_tool()["type"] == "web_fetch_20250910"


def test_fetch_backend_local_builds_our_own_tool(monkeypatch):
    monkeypatch.setenv("FETCH_BACKEND", "local")

    tool = make_fetch_tool()

    assert tool.name == "web_fetch"


def test_local_fetch_tool_limits_calls_and_refuses_hosts(monkeypatch):
    monkeypatch.setenv("FETCH_BACKEND", "local")
    monkeypatch.setenv("WEB_FETCH_MAX_USES", "2")
    tool = make_fetch_tool()

    first = tool.call({"url": "https://evil.example.com/x"})
    second = tool.call({"url": "https://evil.example.com/x"})
    third = tool.call({"url": "https://evil.example.com/x"})

    assert first.startswith("Fetch refused")
    assert second.startswith("Fetch refused")
    assert third == "Fetch limit reached for this ticket"


def test_local_fetch_tool_wraps_body_as_untrusted(monkeypatch, mocker):
    monkeypatch.setenv("FETCH_BACKEND", "local")
    mocker.patch("ticket_classifier.tools.fetch_text", return_value="{}")

    result = make_fetch_tool().call({"url": "https://status.mollie.com/x"})

    assert result == '<fetched url="https://status.mollie.com/x">\n{}\n</fetched>'


def test_code_execution_tool_is_the_server_side_sandbox():
    assert make_code_execution_tool() == {
        "type": "code_execution_20250825",
        "name": "code_execution",
    }
