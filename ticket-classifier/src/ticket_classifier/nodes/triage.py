from typing import Any

from langgraph.types import StreamWriter

from ..client import get_client
from ..config import get_settings
from ..models import TicketClassification, TriageState
from ..prompts import SYSTEM_PROMPT, create_prompt


class TriageError(RuntimeError):
    """The model gave no classification, e.g. a refusal or hitting max_tokens."""


def ignore_event(event: Any) -> None:
    """Default stream writer: drop the event when the node runs outside a graph."""


def node_triage(state: TriageState, writer: StreamWriter = ignore_event) -> TriageState:
    """Classify the ticket with one structured-output call to the model."""
    settings = get_settings()
    ticket = state["ticket"]

    writer({"event": "calling model", "ticket_id": ticket.id, "model": settings.model})

    client = get_client()

    output = client.messages.parse(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": create_prompt(ticket, state["customer"])}
        ],
        output_format=TicketClassification,
    )

    if output.parsed_output is None:
        raise TriageError(
            f"No classification for ticket {ticket.id} "
            f"(stop_reason={output.stop_reason})"
        )
    return {"classification": output.parsed_output}
