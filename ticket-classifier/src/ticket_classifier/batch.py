import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from anthropic import APIError
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from .classifier import ClassificationError
from .graph import TriageState
from .models import (
    ClassifiedTicket,
    Escalated,
    EscalatedTicket,
    ResolvedTicket,
    Ticket,
)
from .trace_graph import log_action

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    classified: list[ClassifiedTicket] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)  # ticket ids
    paused: list[str] = field(default_factory=list)  # ticket ids waiting for a human


def run_ticket(
    workflow: CompiledStateGraph, ticket: Ticket, answer: dict | None = None
) -> TriageState | None:
    """Run one ticket through the workflow and return its final state.

    Each ticket is its own thread, so its checkpoints are stored under the ticket id.
    Returns None while the run is paused for a human. A paused run continues only
    with an ``answer``, which becomes the return value of ``interrupt()``.
    """
    config = {"configurable": {"thread_id": ticket.id}}
    saved = workflow.get_state(config)

    if saved.interrupts:
        if answer is None:
            logger.info("Ticket %s is still waiting for a human answer", ticket.id)
            return None
        logger.info("Resuming paused workflow for ticket %s with %r", ticket.id, answer)
        run_input = Command(resume=answer)
    elif saved.next:
        # A crashed run continues with None as input; a state would start a new run.
        logger.info("Resuming unfinished workflow for ticket %s", ticket.id)
        run_input = None
    else:
        if answer is not None:
            logger.warning("Ticket %s is not paused, ignoring the answer", ticket.id)
        logger.info("Invoking workflow for ticket %s", ticket.id)
        run_input = TriageState(ticket=ticket)

    paused = False
    # "sync" saves each checkpoint before the next step starts, so a killed run
    # can be resumed. "custom" carries events that nodes emit while they work.
    for mode, data in workflow.stream(
        run_input,
        config,
        stream_mode=["updates", "values", "custom"],
        durability="sync",
    ):
        if mode == "custom":  # events a node emits while it works
            logger.info("[custom] %s", data)
        else:
            logger.debug("[%s] %s", mode, data)
        if mode == "updates":
            for node_name, state_updates in data.items():
                if node_name == "__interrupt__":  # a tuple of Interrupt, not a state
                    paused = True
                    requests = [item.value for item in state_updates]
                    logger.info("Ticket %s needs a human: %s", ticket.id, requests)
                    log_action(node_name, "paused for human", {"requests": requests})
                else:
                    log_action(node_name, "state updated", state_updates)
        elif mode == "values":  # full state after each step
            result = data

    if paused:
        return None
    log_action("end", "workflow finished", result)
    return result


def to_classified_ticket(ticket: Ticket, result: TriageState) -> ClassifiedTicket:
    """Turn the final state into a resolved or an escalated ticket."""
    classification = result["classification"]
    escalation = result["escalation"]
    fields = {
        "ticket_id": ticket.id,
        "customer_id": result["customer"].id if result["customer"] else None,
        "category": classification.category,
        "priority": classification.priority,
    }
    if isinstance(escalation, Escalated):
        return EscalatedTicket(**fields, escalation_reason=escalation.escalation_reason)
    return ResolvedTicket(**fields)


def classify_all(
    tickets: list[Ticket],
    approve: Callable[[str], bool],
    log_file_id: str | None = None,
    *,
    workflow: CompiledStateGraph,
    answers: dict[str, dict] | None = None,
) -> BatchResult:
    """Classify every ticket; a failing ticket is recorded and skipped.

    ``answers`` maps a ticket id to a human's answer for its paused run.
    """
    answers = answers or {}
    batch = BatchResult()
    for ticket in tickets:
        try:
            result = run_ticket(workflow, ticket, answers.get(ticket.id))
            if result is None:
                batch.paused.append(ticket.id)
                continue
            classified_ticket = to_classified_ticket(ticket, result)
        except (ClassificationError, APIError) as error:
            batch.failed.append(ticket.id)
            logger.error("Ticket %s failed: %s", ticket.id, error)
            continue

        logger.info("Ticket %s done, result=%s", ticket.id, result["classification"])
        batch.classified.append(classified_ticket)
    return batch
