import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from anthropic import beta_tool
from anthropic.lib.tools import BetaFunctionTool
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


@dataclass
class Escalation:
    """Human gate and outcome of ``escalate_to_human`` for one ticket."""

    approve: Callable[[str], bool]
    reason: str | None = None  # set once a human approved


def make_escalation_tool(escalation: Escalation) -> BetaFunctionTool[Any]:
    """Build ``escalate_to_human``. It only counts once a human approves.

    A rejection is returned to the model as a normal observation so the loop
    continues. After an approval, further calls are answered without asking again.
    """

    @beta_tool
    def escalate_to_human(reason: str) -> str:
        """Hand the ticket to a human agent. Needs approval and may be rejected."""
        logger.info("Escalation requested: %s", reason)
        if escalation.reason is not None:
            return "Already escalated. A human will take over this ticket."
        if not escalation.approve(reason):
            return "Escalation rejected by the human. Continue without escalating."
        escalation.reason = reason
        return "Escalation approved. A human will take over this ticket."

    return escalate_to_human
