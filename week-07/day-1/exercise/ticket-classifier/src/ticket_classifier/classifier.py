from anthropic import Anthropic
from pydantic import ValidationError

from .config import get_settings
from .models import TicketClassification

SYSTEM_PROMPT = (
    "You are a support ticket triage assistant. "
    "Categories: billing (charges, refunds, invoices), technical (bugs, errors, "
    "outages), account (profile, login, settings), other. "
    "Priority: high if the customer is blocked, losing money or threatening to "
    "leave; medium if functionality is impaired; low otherwise."
)


CLASSIFY_TOOL = {
    "name": "classify_ticket",
    "description": "Record the category and priority of a support ticket.",
    "strict": True,
    "input_schema": TicketClassification.model_json_schema(),
}


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

    response = client.messages.create(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": create_prompt(ticket_text)}],
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "any"},
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise ClassificationError(
            f"Model did not call a tool (stop_reason={response.stop_reason})"
        )

    try:
        return TicketClassification.model_validate(tool_use.input)
    except ValidationError as exc:
        raise ClassificationError(f"Invalid tool arguments: {exc}") from exc
