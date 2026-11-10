import logging

from anthropic import Anthropic

from .config import get_settings
from .models import Ticket, TicketClassification
from .tools import lookup_customer

SYSTEM_PROMPT = (
    "You are a support ticket triage assistant. "
    "Categories: billing (charges, refunds, invoices), technical (bugs, errors, "
    "outages), account (profile, login, settings), other. "
    "Priority: high if the customer is blocked, losing money or threatening to "
    "leave; medium if functionality is impaired; low otherwise. "
    "If a customer id is given, call lookup_customer first and use the result. "
    "If none is given, don't call it."
)


logger = logging.getLogger(__name__)


class ClassificationError(RuntimeError):
    """The model did not return a usable classification."""


def create_prompt(ticket: Ticket) -> str:
    if ticket.customer_id is not None:
        return (
            f"Classify the following ticket:\n{ticket}"
            + f"\nCustomer ID: {ticket.customer_id}"
        )
    return f"Classify the following ticket:\n{ticket}"


def create_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key.get_secret_value())


def classify(ticket: Ticket, client: Anthropic | None = None) -> TicketClassification:
    """Classify a support ticket into category and priority.

    Pass a ``client`` to reuse a connection (or to inject a fake in tests).
    """
    client = client or create_client()
    settings = get_settings()

    logger.info("Classifying ticket %s", ticket.id)
    logger.debug("Customer ID: %s", ticket.customer_id)

    runner = client.beta.messages.tool_runner(
        model=settings.model,
        max_iterations=6,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": create_prompt(ticket)}],
        tools=[lookup_customer],
        output_format=TicketClassification,
    )

    final = runner.until_done()

    if final.parsed_output is None:
        raise ClassificationError(f"Failed to classify ticket with ID: {ticket.id}")

    return final.parsed_output
