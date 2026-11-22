import logging

from pydantic import ValidationError

from ..customers import get_customer
from ..models import TriageState
from ..telemetry import CONSOLE_ONLY

logger = logging.getLogger(__name__)


def node_get_customer(state: TriageState) -> TriageState:
    """Look up the ticket's customer; None if there is no id, no match or no data."""
    ticket = state["ticket"]
    if not ticket.customer_id:
        logger.info("Ticket %s has no customer id", ticket.id)
        return {"customer": None}

    try:
        customer = get_customer(ticket.customer_id)
    except OSError, ValidationError:
        # The traceback can quote the customer record, so it stays on the console.
        logger.exception(
            "Cannot read customer %s", ticket.customer_id, extra=CONSOLE_ONLY
        )
        logger.warning("Ticket %s continues without customer data", ticket.id)
        return {"customer": None}

    if customer is None:
        logger.warning("Customer %s not found", ticket.customer_id)
    return {"customer": customer}
