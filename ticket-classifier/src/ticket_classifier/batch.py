import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from anthropic import Anthropic, APIError

from .classifier import ClassificationError
from .graph import TriageState, workflow
from .models import ClassifiedTicket, ResolvedTicket, Ticket

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    classified: list[ClassifiedTicket] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)  # ticket ids


def classify_all(
    tickets: list[Ticket],
    client: Anthropic,
    approve: Callable[[str], bool],
    log_file_id: str | None = None,
) -> BatchResult:
    """Classify every ticket; a failing ticket is recorded and skipped."""
    batch = BatchResult()
    for ticket in tickets:
        try:
            # result = classify(ticket, client, approve, log_file_id)
            state: TriageState = TriageState(
                client=client,
                ticket=ticket,
            )

            logger.info("Invoking workflow for ticket %s", ticket.id)
            result: TriageState = workflow.invoke(state)

            classified_ticket = ResolvedTicket(
                ticket_id=ticket.id,
                customer_id=result["customer"].id if result["customer"] else None,
                category=result["classification"].category,
                priority=result["classification"].priority,
            )

        except (ClassificationError, APIError) as error:
            batch.failed.append(ticket.id)
            logger.error("Ticket %s failed: %s", ticket.id, error)
            continue

        logger.info("Ticket %s done, result=%s", ticket.id, result["classification"])
        batch.classified.append(classified_ticket)
    return batch
