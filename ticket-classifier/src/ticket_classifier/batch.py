import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from anthropic import Anthropic, APIError

from .classifier import ClassificationError, classify
from .models import (
    ClassifiedTicket,
    Escalated,
    EscalatedTicket,
    ResolvedTicket,
    Ticket,
    TriageResult,
)

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    classified: list[ClassifiedTicket] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)  # ticket ids


def to_classified_ticket(ticket: Ticket, triage: TriageResult) -> ClassifiedTicket:
    classification = triage.classification
    category = classification.category if classification else None
    priority = classification.priority if classification else None
    if isinstance(triage, Escalated):
        return EscalatedTicket(
            ticket_id=ticket.id,
            customer_id=ticket.customer_id,
            category=category,
            priority=priority,
            escalation_reason=triage.escalation_reason,
        )
    return ResolvedTicket(
        ticket_id=ticket.id,
        customer_id=ticket.customer_id,
        category=triage.classification.category,
        priority=triage.classification.priority,
    )


def classify_all(
    tickets: list[Ticket], client: Anthropic, approve: Callable[[str], bool]
) -> BatchResult:
    """Classify every ticket; a failing ticket is recorded and skipped."""
    batch = BatchResult()
    for ticket in tickets:
        try:
            triage = classify(ticket, client, approve)
        except (ClassificationError, APIError) as error:
            batch.failed.append(ticket.id)
            logger.error("Ticket %s failed: %s", ticket.id, error)
            continue

        logger.info("Ticket %s done, escalated=%s", ticket.id, triage.escalated)
        batch.classified.append(to_classified_ticket(ticket, triage))
    return batch
