import logging

from langgraph.types import interrupt

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


def escalation_request(state: TriageState) -> dict:
    """What a person needs to decide whether to take over the ticket."""
    ticket = state["ticket"]
    customer = state.get("customer")
    classification = state["classification"]
    return {
        "question": "High priority ticket. Should a human take over?",
        "answer_format": {"approved": "bool", "note": "str"},
        "ticket": ticket.model_dump(mode="json"),
        "customer": customer.model_dump(mode="json") if customer else None,
        "classification": classification.model_dump(mode="json"),
    }


def node_wait_for_human(state: TriageState) -> TriageState:
    """Pause the run until a person answers with {"approved": bool, "note": str}."""
    # Runs again on resume: everything above interrupt() must be safe to repeat.
    logger.debug("node_wait_for_human started for ticket %s", state["ticket"].id)

    answer = interrupt(escalation_request(state))
    logger.info("Human answer: %r", answer)

    note = answer.get("note", "")
    if answer["approved"]:
        escalation = Escalated(escalation_reason=note or "High priority ticket")
        response = f"Human took over. Note: {note}"
    else:
        escalation = NotEscalated()
        response = f"Human declined to take over. Note: {note}"

    return {
        "last_updated_by": "node_wait_for_human",
        "escalation": escalation,
        "responses": [response],
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
