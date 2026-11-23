"""Run tickets through the workflow: one thread per ticket, every run streamed."""

from dataclasses import dataclass, field

from anthropic import APIError
from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from .checkpoint import run_status, thread_config
from .models import (
    ClassifiedTicket,
    Escalated,
    EscalatedTicket,
    HumanAnswer,
    ResolvedTicket,
    Ticket,
    TriageState,
)
from .nodes import TriageError
from .telemetry import (
    get_loggers,
    record_classification,
    record_failure,
    record_pause,
    record_reused,
    record_status,
    ticket_span,
)
from .trace import trace_event

logger, safe_log = get_loggers(__name__)


@dataclass
class BatchResult:
    classified: list[ClassifiedTicket] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)  # ticket ids
    paused: list[str] = field(default_factory=list)  # ticket ids waiting for a human


class NotPausedError(LookupError):
    """There is no paused run for this ticket id."""


def run_all(tickets: list[Ticket], *, workflow: CompiledStateGraph) -> BatchResult:
    """Run every ticket; a failing ticket is recorded and skipped."""
    batch = BatchResult()
    for ticket in tickets:
        with ticket_span(ticket.id, "run"):
            try:
                result = run_ticket(workflow, ticket)
            except (APIError, TriageError) as error:
                batch.failed.append(ticket.id)
                safe_log.error("Ticket %s failed: %s", ticket.id, type(error).__name__)
                logger.error("Ticket %s error detail: %s", ticket.id, error)
                record_failure(error)
                continue

            if result is None:
                batch.paused.append(ticket.id)
                continue
            classification = result["classification"]
            safe_log.info("Ticket %s done, result=%s", ticket.id, classification)
            batch.classified.append(to_classified_ticket(result))
    return batch


def run_ticket(workflow: CompiledStateGraph, ticket: Ticket) -> TriageState | None:
    """Run one ticket and return its final state; None while it waits for a human.

    A paused run stays paused until ``resume_ticket`` answers it, an unfinished run
    continues where it stopped, a finished run returns its saved state.
    """
    saved = workflow.get_state(thread_config(ticket.id))

    record_classification(saved.values)  # a paused or finished run has one already

    match run_status(saved):
        case "paused":
            record_reused("paused")
            safe_log.info("Ticket %s is still waiting for a human answer", ticket.id)
            return None
        case "unfinished":
            # None as input continues the saved run; a state would start a new one.
            safe_log.info("Continuing unfinished run of ticket %s", ticket.id)
            return run_thread(workflow, None, ticket.id)
        case "finished":
            record_reused("finished")
            safe_log.info(
                "Ticket %s already finished, using the saved result", ticket.id
            )
            return saved.values
        case "new":
            safe_log.info("Starting run of ticket %s", ticket.id)
            return run_thread(workflow, TriageState(ticket=ticket), ticket.id)


def resume_ticket(
    workflow: CompiledStateGraph, ticket_id: str, answer: HumanAnswer
) -> TriageState | None:
    """Answer a paused run; ``answer`` becomes the return value of ``interrupt()``.

    Raises ``NotPausedError`` if the ticket has no paused run.
    """
    saved = workflow.get_state(thread_config(ticket_id))

    if run_status(saved) != "paused":
        raise NotPausedError(f"Ticket {ticket_id} has no paused run")

    safe_log.info("Resuming ticket %s", ticket_id)
    logger.info("Ticket %s resume answer: %r", ticket_id, answer)

    return run_thread(workflow, Command(resume=answer), ticket_id)


def run_thread(
    workflow: CompiledStateGraph,
    run_input: TriageState | Command | None,
    ticket_id: str,
) -> TriageState | None:
    """Every run goes through here: stream it, log and trace each node update.

    Returns the final state, or None if the run paused for a human.
    """
    config = thread_config(ticket_id)
    # "sync" saves each checkpoint before the next step starts, so a killed run
    # can continue. "custom" carries events that nodes emit while they work.

    stream = workflow.stream(
        run_input, config, stream_mode=["updates", "custom"], durability="sync"
    )

    for mode, data in stream:
        if mode == "custom":
            logger.info("[custom] %s", data)
            continue
        logger.debug("[updates] %s", data)
        for node_name, update in data.items():
            if node_name != "__interrupt__":  # the pause is read from the state below
                trace_event(ticket_id, node_name, "updated", update)

    state = workflow.get_state(config)

    record_classification(state.values)

    if state.interrupts:
        requests = [item.value for item in state.interrupts]
        safe_log.info("Ticket %s needs a human at %s", ticket_id, state.next[0])
        logger.info("Ticket %s review request: %s", ticket_id, requests)
        trace_event(ticket_id, state.next[0], "paused", {"requests": requests})
        record_pause(state.next[0])
        return None
    record_status("finished")
    trace_event(ticket_id, END, "finished", state.values)
    return state.values


def to_classified_ticket(result: TriageState) -> ClassifiedTicket:
    """Turn the final state into a resolved or an escalated ticket."""
    classification = result["classification"]
    escalation = result["escalation"]
    fields = {
        "ticket_id": result["ticket"].id,
        "customer_id": result["customer"].id if result["customer"] else None,
        "category": classification.category,
        "priority": classification.priority,
    }
    if isinstance(escalation, Escalated):
        return EscalatedTicket(**fields, escalation_reason=escalation.escalation_reason)
    return ResolvedTicket(**fields)
