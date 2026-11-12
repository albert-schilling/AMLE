import json

from ticket_classifier.tools import (
    Escalation,
    lookup_customer,
    make_escalation_tool,
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
    assert tool["allowed_domains"] == ["status.mollie.com"]
    assert tool["max_content_tokens"] > 0


def test_web_fetch_guardrails_follow_settings(monkeypatch):
    monkeypatch.setenv("STATUS_DOMAIN", "status.example.com")
    monkeypatch.setenv("WEB_FETCH_MAX_USES", "1")

    tool = make_web_fetch_tool()

    assert tool["allowed_domains"] == ["status.example.com"]
    assert tool["max_uses"] == 1
