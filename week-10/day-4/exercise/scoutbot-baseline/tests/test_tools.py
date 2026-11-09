from scoutbot.tools import escalate_to_human, look_up_customer


def test_look_up_customer_known_id():
    result = look_up_customer("1001")
    assert result["found"] is True
    assert result["plan"] == "pro"


def test_look_up_customer_unknown_id_is_graceful():
    result = look_up_customer("does-not-exist")
    assert result == {"found": False, "customer_id": "does-not-exist"}


def test_escalate_to_human_approved():
    result = escalate_to_human("needs a refund decision", approve_fn=lambda reason: True)
    assert result["approved"] is True


def test_escalate_to_human_rejected():
    result = escalate_to_human("needs a refund decision", approve_fn=lambda reason: False)
    assert result["approved"] is False


def test_escalate_to_human_passes_reason_to_approve_fn():
    seen = []
    escalate_to_human("a specific reason", approve_fn=lambda reason: seen.append(reason) or True)
    assert seen == ["a specific reason"]
