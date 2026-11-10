import json

from ticket_classifier.tools import lookup_customer, make_escalation_tool


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
    approved = []
    tool = make_escalation_tool(lambda reason: True, approved)

    result = tool.call({"reason": "legal threat"})

    assert approved == ["legal threat"]
    assert "approved" in result


def test_rejected_escalation_is_an_observation_not_an_effect():
    approved = []
    tool = make_escalation_tool(lambda reason: False, approved)

    result = tool.call({"reason": "legal threat"})

    assert approved == []
    assert "rejected" in result
