import logging

from ticket_classifier.customers import get_customer
from ticket_classifier.graph import TriageState

logger = logging.getLogger(__name__)


def node_get_customer(state: TriageState) -> TriageState:
    customer = None
    response = None

    customer_id = state["ticket"].customer_id

    if customer_id:
        try:
            customer = get_customer(customer_id)
            response = f"Successfully retrieved customer with ID: {customer_id}"
            logger.info("Successfully retrieved customer with ID: %s", customer_id)

        except Exception:
            response = f'Failed to get customer with ID "{customer_id}".'
            logger.error("Failed to get customer with ID: %s", customer_id)

    # partial state update
    return {
        "last_updated_by": "node_get_customer",
        "customer": customer,
        "responses": [response],
    }
