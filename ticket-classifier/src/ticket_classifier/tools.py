import json
import logging

from anthropic import beta_tool

from .config import get_settings
from .models import Customer

logger = logging.getLogger(__name__)


@beta_tool
def lookup_customer(customer_id: str) -> str:
    """Look up a customer by id. Returns customer JSON or 'Customer not found'."""
    logger.info("Looking up customer %s", customer_id)

    customers = json.loads(get_settings().customers_path.read_text(encoding="utf-8"))
    customer = customers.get(customer_id)

    if customer is None:
        logger.warning("Customer %s not found", customer_id)
        return "Customer not found"

    return Customer(**customer).model_dump_json()
