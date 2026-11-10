import logging
from dataclasses import dataclass, field

from anthropic import Anthropic, APIError

from .classifier import ClassificationError, classify
from .models import ClassifiedTicket, Ticket

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    classified: list[ClassifiedTicket] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)  # ticket ids


def classify_all(tickets: list[Ticket], client: Anthropic) -> BatchResult:
    """Classify every ticket; a failing ticket is recorded and skipped."""
    batch = BatchResult()
    for ticket in tickets:
        try:
            result = classify(ticket, client=client)
        except (ClassificationError, APIError) as error:
            batch.failed.append(ticket.id)
            logger.error("Ticket %s failed: %s", ticket.id, error)
            continue

        logger.info("Ticket %s -> %s / %s", ticket.id, result.category, result.priority)
        batch.classified.append(
            ClassifiedTicket(
                ticket_id=ticket.id,
                customer_id=ticket.customer_id,
                category=result.category,
                priority=result.priority,
            )
        )
    return batch
