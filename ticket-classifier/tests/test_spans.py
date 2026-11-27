import pytest
from helpers import HIGH, REFUND_PASSAGE, reply_message
from pydantic import ValidationError

from ticket_classifier.cli import main
from ticket_classifier.models import KnowledgePassage, TicketClassification

PRIVATE_PASSAGE = KnowledgePassage(
    source="refunds.md", ordinal=1, text="private policy text", score=0.9
)


def by_name(spans, name):
    return [span for span in spans if span.name == name]


def test_run_has_one_root_span_with_one_child_per_ticket(
    model, write_tickets, finished_spans
):
    tickets = write_tickets(
        [{"id": "T-1", "text": "first"}, {"id": "T-2", "text": "second"}]
    )

    assert main(["run", str(tickets)]) == 0

    spans = finished_spans()
    (root,) = by_name(spans, "ticket-classifier run")
    children = by_name(spans, "ticket.run")
    assert root.parent is None
    assert len(children) == 2
    assert all(c.parent.span_id == root.context.span_id for c in children)
    assert {c.context.trace_id for c in children} == {root.context.trace_id}


def test_failed_ticket_marks_its_span_as_error(model, write_tickets, finished_spans):
    model.outcomes["broken"] = None  # no classification: the ticket fails
    tickets = write_tickets(
        [{"id": "T-1", "text": "broken"}, {"id": "T-2", "text": "fine"}]
    )

    assert main(["run", str(tickets)]) == 1

    failed, fine = by_name(finished_spans(), "ticket.run")
    assert failed.status.status_code.name == "ERROR"
    assert failed.events[0].name == "exception"
    assert fine.status.status_code.name == "UNSET"


def test_resume_has_root_span_with_ticket_span(model, write_tickets, finished_spans):
    model.outcomes["urgent"] = HIGH  # high priority: pauses for a human
    main(["run", str(write_tickets([{"id": "T-1", "text": "urgent"}]))])

    assert main(["resume", "T-1", "--approve", "--note", "ok"]) == 0

    spans = finished_spans()
    (root,) = by_name(spans, "ticket-classifier resume")
    (ticket,) = by_name(spans, "ticket.resume")
    assert ticket.parent.span_id == root.context.span_id


def test_ticket_span_has_ids_mode_and_classification(
    model, write_tickets, finished_spans
):
    model.outcomes["urgent"] = HIGH
    main(["run", str(write_tickets([{"id": "T-1", "text": "urgent"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["ticket_id"] == "T-1"
    assert span.attributes["thread_id"] == "T-1"
    assert span.attributes["run_mode"] == "run"
    assert span.attributes["category"] == HIGH.category
    assert span.attributes["priority"] == "high"


def test_ticket_span_has_policy_citations_and_top_score(
    model, knowledge, write_tickets, finished_spans
):
    second = REFUND_PASSAGE.model_copy(update={"ordinal": 2, "score": 0.7})
    knowledge.passages = [REFUND_PASSAGE, second]
    main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["knowledge.passages"] == 2
    assert span.attributes["knowledge.sources"] == ("refunds.md#1", "refunds.md#2")
    assert span.attributes["knowledge.top_score"] == 0.9


def test_ticket_span_counts_passages_below_the_minimum_score(
    model, knowledge, write_tickets, finished_spans
):
    weak = REFUND_PASSAGE.model_copy(update={"ordinal": 2, "score": 0.1})
    knowledge.passages = [REFUND_PASSAGE, weak]
    main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["knowledge.passages"] == 1
    assert span.attributes["knowledge.dropped"] == 1


def test_ticket_span_has_reply_citations(
    model, reply_api, write_tickets, finished_spans
):
    reply_api.return_value = reply_message(
        {"text": "Refunds take 5 days.", "cited": [(0, "5 days")]}
    )
    main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["reply.citations"] == 1
    assert span.attributes["reply.sources"] == ("refunds.md#1",)
    assert span.attributes["reply.has_sources"] is True


def test_ticket_span_marks_a_reply_without_sources(
    model, write_tickets, finished_spans
):
    main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["reply.citations"] == 0
    assert span.attributes["reply.has_sources"] is False


def test_ticket_span_has_search_attempts_and_verdict(
    model, knowledge, write_tickets, finished_spans, monkeypatch
):
    monkeypatch.setenv("KNOWLEDGE_MAX_ATTEMPTS", "2")
    knowledge.passages = []
    main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["knowledge.attempts"] == 2
    assert span.attributes["knowledge.retrieval_ok"] is False


def test_ticket_span_without_passages_has_no_top_score(
    model, knowledge, write_tickets, finished_spans
):
    knowledge.passages = []
    main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["knowledge.passages"] == 0
    assert "knowledge.top_score" not in span.attributes


def test_second_run_of_a_paused_ticket_keeps_classification(
    model, write_tickets, finished_spans
):
    model.outcomes["urgent"] = HIGH
    tickets = write_tickets([{"id": "T-1", "text": "urgent"}])
    main(["run", str(tickets)])
    main(["run", str(tickets)])

    _, second = by_name(finished_spans(), "ticket.run")
    assert second.attributes["priority"] == "high"
    assert model.call_count == 1


def test_resume_span_has_ids_and_classification(model, write_tickets, finished_spans):
    model.outcomes["urgent"] = HIGH
    main(["run", str(write_tickets([{"id": "T-1", "text": "urgent"}]))])
    main(["resume", "T-1", "--approve", "--note", "ok"])

    (span,) = by_name(finished_spans(), "ticket.resume")
    assert span.attributes["ticket_id"] == "T-1"
    assert span.attributes["run_mode"] == "resume"
    assert span.attributes["priority"] == "high"


def test_failed_ticket_span_has_no_classification(model, write_tickets, finished_spans):
    model.outcomes["broken"] = None
    main(["run", str(write_tickets([{"id": "T-1", "text": "broken"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["ticket_id"] == "T-1"
    assert "priority" not in span.attributes


def test_pause_marks_span_without_error(model, write_tickets, finished_spans):
    model.outcomes["urgent"] = HIGH
    main(["run", str(write_tickets([{"id": "T-1", "text": "urgent"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["ticket.status"] == "paused"
    assert span.status.status_code.name == "UNSET"
    (event,) = span.events
    assert event.name == "paused"
    assert event.attributes["node"] == "human_review"


def test_second_run_of_paused_ticket_is_waiting_without_new_event(
    model, write_tickets, finished_spans
):
    model.outcomes["urgent"] = HIGH
    tickets = write_tickets([{"id": "T-1", "text": "urgent"}])
    main(["run", str(tickets)])
    main(["run", str(tickets)])

    _, second = by_name(finished_spans(), "ticket.run")
    assert second.attributes["ticket.status"] == "paused"
    assert not second.events


def test_finished_ticket_is_not_marked_paused(model, write_tickets, finished_spans):
    model.outcomes["urgent"] = HIGH
    main(
        [
            "run",
            str(
                write_tickets(
                    [{"id": "T-1", "text": "urgent"}, {"id": "T-2", "text": "calm"}]
                )
            ),
        ]
    )
    main(["resume", "T-1", "--approve", "--note", "ok"])

    spans = finished_spans()
    _, calm = by_name(spans, "ticket.run")
    (resumed,) = by_name(spans, "ticket.resume")
    assert calm.attributes["ticket.status"] == "finished"
    assert resumed.attributes["ticket.status"] == "finished"


def test_failed_ticket_has_failed_status(model, write_tickets, finished_spans):
    model.outcomes["broken"] = None
    main(["run", str(write_tickets([{"id": "T-1", "text": "broken"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.attributes["ticket.status"] == "failed"
    assert "ticket.reused" not in span.attributes


def test_only_a_run_without_work_is_marked_reused(model, write_tickets, finished_spans):
    tickets = write_tickets([{"id": "T-1", "text": "calm"}])
    main(["run", str(tickets)])
    main(["run", str(tickets)])

    first, second = by_name(finished_spans(), "ticket.run")
    assert "ticket.reused" not in first.attributes
    assert second.attributes["ticket.reused"] is True
    assert second.attributes["ticket.status"] == "finished"


def test_spans_hold_no_ticket_customer_policy_query_or_reply_text(
    model, knowledge, reply_api, write_tickets, finished_spans, private_query_writer
):
    knowledge.passages = [PRIVATE_PASSAGE]
    reply_api.return_value = reply_message(
        {"text": "private reply text", "cited": [(0, "private policy text")]}
    )
    model.outcomes["private urgent text"] = HIGH
    model.outcomes["private broken text"] = None
    tickets = write_tickets(
        [
            {"id": "T-1", "customer_id": "1001", "text": "private urgent text"},
            {"id": "T-2", "customer_id": "1001", "text": "private broken text"},
        ]
    )
    main(["run", str(tickets)])
    main(["resume", "T-1", "--approve", "--note", "private reviewer note"])

    exported = " ".join(span.to_json() for span in finished_spans())
    private_texts = (
        "private urgent",
        "private broken",
        "private reviewer",
        "private policy",
        "private reply",
        "private query",
        "alice",
    )
    for private in private_texts:
        assert private not in exported.lower()


def test_resume_without_paused_run_marks_span_as_error(model, finished_spans):
    assert main(["resume", "T-404", "--approve", "--note", "x"]) == 2

    (span,) = by_name(finished_spans(), "ticket.resume")
    assert span.attributes["ticket_id"] == "T-404"
    assert span.status.status_code.name == "ERROR"


def test_invalid_model_output_fails_one_ticket_without_its_text(
    model, write_tickets, finished_spans
):
    with pytest.raises(ValidationError) as caught:
        TicketClassification.model_validate_json("private model text")
    model.outcomes["bad output"] = caught.value
    tickets = write_tickets(
        [{"id": "T-1", "text": "bad output"}, {"id": "T-2", "text": "fine"}]
    )

    assert main(["run", str(tickets)]) == 1

    failed, fine = by_name(finished_spans(), "ticket.run")
    assert failed.attributes["ticket.status"] == "failed"
    assert fine.attributes["ticket.status"] == "finished"
    assert "private model text" not in failed.to_json()


def test_failure_span_has_error_type_but_not_its_text(
    model, write_tickets, finished_spans
):
    model.outcomes["broken"] = None
    main(["run", str(write_tickets([{"id": "T-1", "text": "broken"}]))])

    (span,) = by_name(finished_spans(), "ticket.run")
    assert span.status.description == "TriageError"
    assert span.events[0].attributes["exception.type"] == "TriageError"
    assert "exception.message" not in span.events[0].attributes
