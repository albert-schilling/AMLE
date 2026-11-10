import logging

from anthropic import Anthropic

from .config import get_settings
from .models import Ticket, TicketClassification
from .prompts import SYSTEM_PROMPT, create_prompt
from .tools import lookup_customer

logger = logging.getLogger(__name__)


class ClassificationError(RuntimeError):
    """The model did not return a usable classification."""


def create_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key.get_secret_value())


def classify(ticket: Ticket, client: Anthropic) -> TicketClassification:
    """Classify a support ticket into category and priority."""
    settings = get_settings()

    logger.info("Classifying ticket %s", ticket.id)
    logger.debug("Customer ID: %s", ticket.customer_id)

    runner = client.beta.messages.tool_runner(
        model=settings.model,
        max_iterations=settings.max_iterations,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": create_prompt(ticket)}],
        tools=[lookup_customer],
        output_format=TicketClassification,
    )

    final = runner.until_done()
    logger.debug("Ticket %s finished, stop_reason=%s", ticket.id, final.stop_reason)

    if final.parsed_output is None:
        raise ClassificationError(
            f"No parsed classification for ticket {ticket.id} "
            f"(stop_reason={final.stop_reason})"
        )

    return final.parsed_output
