import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from anthropic import APIError
from langgraph.graph.state import CompiledStateGraph

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


def run_ticket(workflow: CompiledStateGraph, ticket: Ticket) -> TriageState:
    """Run one ticket through the workflow and return its final state.

    Each ticket is its own thread, so its checkpoints are stored under the ticket id.
    """
    config = {"configurable": {"thread_id": ticket.id}}

    # An unfinished saved run continues with None as input; a state would start a
    # new run instead.
    if workflow.get_state(config).next:
        logger.info("Resuming unfinished workflow for ticket %s", ticket.id)
        run_input = None
    else:
        logger.info("Invoking workflow for ticket %s", ticket.id)
        run_input = TriageState(ticket=ticket)

    # "sync" saves each checkpoint before the next step starts, so a killed run
    # can be resumed.
    for mode, data in workflow.stream(
        run_input, config, stream_mode=["updates", "values"], durability="sync"
    ):
        if mode == "updates":
            for node_name, state_updates in data.items():
                log_action(node_name, "state updated", state_updates)
        else:  # "values": full state after each step
            result = data

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
) -> BatchResult:
    """Classify every ticket; a failing ticket is recorded and skipped."""
    batch = BatchResult()
    for ticket in tickets:
        try:
            result = run_ticket(workflow, ticket)
            classified_ticket = to_classified_ticket(ticket, result)
        except (ClassificationError, APIError) as error:
            batch.failed.append(ticket.id)
            logger.error("Ticket %s failed: %s", ticket.id, error)
            continue

        logger.info("Ticket %s done, result=%s", ticket.id, result["classification"])
        batch.classified.append(classified_ticket)
    return batch
