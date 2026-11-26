import pytest
from helpers import LOW, REFUND_PASSAGE, searched

from ticket_classifier.config import get_settings
from ticket_classifier.graph import build_workflow
from ticket_classifier.models import TicketClassification, initial_state
from ticket_classifier.nodes import TriageError, node_triage
from ticket_classifier.nodes.names import TRIAGE
from ticket_classifier.prompts import SYSTEM_PROMPT


def test_calls_the_model_with_prompt_and_schema(model, make_ticket):
    update = node_triage(
        {
            "ticket": make_ticket(text="My card was charged twice"),
            "customer": None,
            "search": searched(),
        }
    )

    kwargs = model.call_args.kwargs
    assert kwargs["system"] == SYSTEM_PROMPT
    assert kwargs["output_format"] is TicketClassification
    assert kwargs["max_tokens"] == get_settings().max_tokens
    assert "My card was charged twice" in kwargs["messages"][0]["content"]
    assert update == {"classification": LOW}


def test_no_parsed_output_raises(model, make_ticket):
    model.outcomes["Test ticket"] = None

    with pytest.raises(TriageError, match="T-1.*max_tokens"):
        node_triage(
            {
                "ticket": make_ticket(id="T-1"),
                "customer": None,
                "search": searched(),
            }
        )


def test_custom_event_arrives_before_the_node_update(
    model, mocker, make_ticket, workflow_context
):
    chunks = list(
        build_workflow().stream(
            initial_state(make_ticket(id="T-1")),
            context=workflow_context,
            stream_mode=["updates", "custom"],
        )
    )

    custom = chunks.index(
        ("custom", {"event": "calling model", "ticket_id": "T-1", "model": mocker.ANY})
    )
    triage_update = next(
        i
        for i, (mode, data) in enumerate(chunks)
        if mode == "updates" and TRIAGE in data
    )
    assert custom < triage_update


def test_retrieved_passages_reach_the_prompt(model, make_ticket):
    node_triage(
        {
            "ticket": make_ticket(),
            "customer": None,
            "search": searched(REFUND_PASSAGE),
        }
    )

    assert REFUND_PASSAGE.text in model.call_args.kwargs["messages"][0]["content"]
