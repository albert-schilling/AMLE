"""The reply node alone and in the real graph; the API is faked."""

from helpers import HIGH, REFUND_PASSAGE, reply_message, retrieved

from ticket_classifier.config import get_settings
from ticket_classifier.graph import build_workflow
from ticket_classifier.nodes import node_draft_reply
from ticket_classifier.prompts import REPLY_SYSTEM_PROMPT


def state(make_ticket, *passages):
    return {
        "ticket": make_ticket(text="Where is my refund?"),
        "customer": None,
        "classification": HIGH,
        "retrieval": retrieved(*passages),
    }


def test_sends_the_passages_as_search_results_and_returns_the_reply(
    reply_api, make_ticket
):
    reply_api.return_value = reply_message(
        {"text": "Refunds take 5 days.", "cited": [(0, "Refunds take 5")]}
    )

    update = node_draft_reply(state(make_ticket, REFUND_PASSAGE))

    kwargs = reply_api.call_args.kwargs
    assert kwargs["system"] == REPLY_SYSTEM_PROMPT
    content = kwargs["messages"][0]["content"]
    assert [block["type"] for block in content] == ["text", "search_result", "text"]
    assert content[1]["source"] == "refunds.md#1"
    assert update["reply"].citations[0].citation == "refunds.md#1"


def test_without_passages_sends_no_search_results(reply_api, make_ticket):
    update = node_draft_reply(state(make_ticket))

    content = reply_api.call_args.kwargs["messages"][0]["content"]
    assert [block["type"] for block in content] == ["text", "text"]
    assert not update["reply"].has_sources


def test_uses_reply_model_and_falls_back_to_model(reply_api, make_ticket, monkeypatch):
    monkeypatch.setenv("MODEL", "triage-model")
    monkeypatch.setenv("REPLY_MAX_TOKENS", "321")
    node_draft_reply(state(make_ticket))
    assert reply_api.call_args.kwargs["model"] == "triage-model"
    assert reply_api.call_args.kwargs["max_tokens"] == 321

    monkeypatch.setenv("REPLY_MODEL", "reply-model")
    get_settings.cache_clear()
    node_draft_reply(state(make_ticket))
    assert reply_api.call_args.kwargs["model"] == "reply-model"


def test_reply_is_drafted_after_triage_and_before_the_router():
    edges = {(e.source, e.target) for e in build_workflow().get_graph().edges}

    assert ("triage", "draft_reply") in edges
    assert ("draft_reply", "human_review") in edges
    assert ("draft_reply", "mark_handled") in edges
    assert ("triage", "human_review") not in edges
