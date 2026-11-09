from anthropic import Anthropic

from .config import get_settings
from .models import TicketClassification

SYSTEM_PROMPT = (
    "You are a support ticket triage assistant. "
    "Categories: billing (charges, refunds, invoices), technical (bugs, errors, "
    "outages), account (profile, login, settings), other. "
    "Priority: high if the customer is blocked, losing money or threatening to "
    "leave; medium if functionality is impaired; low otherwise."
)


class ClassificationError(RuntimeError):
    """The model did not return a usable classification."""


def create_prompt(ticket_text: str) -> str:
    return f"Classify the following ticket:\n{ticket_text}"


def create_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key.get_secret_value())


def classify(ticket_text: str, client: Anthropic | None = None) -> TicketClassification:
    """Classify a support ticket into category and priority.

    Pass a ``client`` to reuse a connection (or to inject a fake in tests).
    """
    client = client or create_client()
    settings = get_settings()

    response = client.messages.parse(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": create_prompt(ticket_text)}],
        output_format=TicketClassification,
    )

    classification = response.parsed_output

    if classification is None:
        raise ClassificationError(
            f"No classification returned (stop_reason={response.stop_reason})"
        )

    return classification
