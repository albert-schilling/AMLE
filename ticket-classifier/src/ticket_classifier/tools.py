import logging

from anthropic import beta_tool
from pydantic import ValidationError

from .customers import get_customer

logger = logging.getLogger(__name__)


@beta_tool
def lookup_customer(customer_id: str) -> str:
    """Look up a customer by id. Returns customer JSON or an error message."""
    logger.info("Looking up customer %s", customer_id)

    try:
        customer = get_customer(customer_id)
    except ValidationError:
        logger.exception("Customer record %s is malformed", customer_id)
        return "Customer record unavailable"

    if customer is None:
        logger.warning("Customer %s not found", customer_id)
        return "Customer not found"

    return customer.model_dump_json()
