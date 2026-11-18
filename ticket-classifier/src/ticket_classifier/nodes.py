import logging

from ticket_classifier.customers import get_customer
from ticket_classifier.models import Escalated, NotEscalated, TriageState

logger = logging.getLogger(__name__)


def node_get_customer(state: TriageState) -> TriageState:
    customer = None
    customer_id = state["ticket"].customer_id

    if not customer_id:
        message = "Ticket has no customer ID."
        logger.info(message)
    else:
        try:
            customer = get_customer(customer_id)
        except Exception:
            message = f'Failed to get customer with ID "{customer_id}".'
            logger.error(message)
        else:
            if customer is None:
                message = f'Customer with ID "{customer_id}" not found.'
                logger.warning(message)
            else:
                message = f"Successfully retrieved customer with ID: {customer_id}"
                logger.info(message)

    # partial state update
    return {
        "last_updated_by": "node_get_customer",
        "customer": customer,
        "responses": [message],
    }


def node_wait_for_human(state: TriageState) -> TriageState:
    """Terminal node: record that a person needs to look at this ticket."""
    return {
        "last_updated_by": "node_wait_for_human",
        "escalation": Escalated(escalation_reason="High priority ticket"),
        "responses": ["Waiting for a human"],
    }


def node_mark_handled(state: TriageState) -> TriageState:
    """Terminal node: record that the ticket was handled automatically."""
    return {
        "last_updated_by": "node_mark_handled",
        "escalation": NotEscalated(),
        "responses": ["Handled automatically"],
    }


def route_after_triage(state: TriageState) -> str:
    """Pick the next node from the classification: high priority goes to a human."""
    if state["classification"].priority == "high":
        return "node_wait_for_human"
    return "node_mark_handled"
