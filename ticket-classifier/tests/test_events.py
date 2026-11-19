from ticket_classifier.graph import build_workflow
from ticket_classifier.models import TicketClassification


def test_custom_event_arrives_before_the_node_update(mocker, make_ticket):
    classification = TicketClassification(category="billing", priority="low")
    client = mocker.patch("ticket_classifier.triage_node.get_client").return_value
    client.messages.parse.return_value.content = [
        mocker.Mock(parsed_output=classification)
    ]
    mocker.patch("ticket_classifier.nodes.get_customer", return_value=None)
    workflow = build_workflow()

    chunks = list(
        workflow.stream(
            {"ticket": make_ticket(id="T-1")}, stream_mode=["updates", "custom"]
        )
    )

    custom = chunks.index(
        ("custom", {"event": "calling model", "ticket_id": "T-1", "model": mocker.ANY})
    )
    triage_update = next(
        i
        for i, (mode, data) in enumerate(chunks)
        if mode == "updates" and "node_triage" in data
    )
    assert custom < triage_update
