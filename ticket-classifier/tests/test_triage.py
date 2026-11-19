import pytest
from helpers import LOW

from ticket_classifier.graph import build_workflow
from ticket_classifier.nodes import TriageError, node_triage
from ticket_classifier.nodes.names import TRIAGE


def test_returns_the_classification(model, make_ticket):
    update = node_triage({"ticket": make_ticket(), "customer": None})

    assert update == {"classification": LOW}


def test_no_parsed_output_raises(model, make_ticket):
    model.outcomes["Test ticket"] = None

    with pytest.raises(TriageError, match="T-1.*max_tokens"):
        node_triage({"ticket": make_ticket(id="T-1"), "customer": None})


def test_custom_event_arrives_before_the_node_update(model, mocker, make_ticket):

    chunks = list(
        build_workflow().stream(
            {"ticket": make_ticket(id="T-1")}, stream_mode=["updates", "custom"]
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
