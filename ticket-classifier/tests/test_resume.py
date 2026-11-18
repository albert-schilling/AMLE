from langgraph.checkpoint.memory import InMemorySaver

from ticket_classifier.batch import classify_all
from ticket_classifier.graph import build_workflow
from ticket_classifier.models import EscalatedTicket, TicketClassification


def test_resumed_run_does_not_call_the_model_again(mocker, make_ticket):
    ticket = make_ticket(id="T-1")
    classification = TicketClassification(category="billing", priority="high")
    client = mocker.patch("ticket_classifier.triage_node.get_client").return_value
    client.messages.parse.return_value.content = [
        mocker.Mock(parsed_output=classification)
    ]
    mocker.patch("ticket_classifier.nodes.get_customer", return_value=None)
    mocker.patch("ticket_classifier.batch.log_action")
    workflow = build_workflow(InMemorySaver())
    config = {"configurable": {"thread_id": "T-1"}}

    # First run stops right after triage, before the last node.
    for values in workflow.stream({"ticket": ticket}, config, stream_mode="values"):
        if values.get("classification"):
            break
    assert workflow.get_state(config).next == ("node_wait_for_human",)

    batch = classify_all([ticket], lambda reason: False, workflow=workflow)

    assert isinstance(batch.classified[0], EscalatedTicket)
    assert client.messages.parse.call_count == 1
