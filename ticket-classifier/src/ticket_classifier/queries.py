"""The search query for a ticket, written by the model."""

from pydantic import ValidationError

from .client import get_client
from .config import get_settings
from .models import Search, SearchQuery, Ticket
from .prompts import QUERY_SYSTEM_PROMPT, REWORD_SYSTEM_PROMPT, query_prompt
from .telemetry import get_loggers

logger, safe_log = get_loggers(__name__)

QUERY_MAX_TOKENS = 200  # a few keywords


def write_query(ticket: Ticket, search: Search) -> str:
    """The next search query for the ticket; after a failed search, a reworded one.

    Falls back to the ticket text if the model gives no usable query. An
    ``APIError`` is raised: the ticket fails like a triage failure.
    """
    settings = get_settings()
    system = REWORD_SYSTEM_PROMPT if search.attempts else QUERY_SYSTEM_PROMPT
    content = query_prompt(ticket, search)

    try:
        output = get_client().messages.parse(
            model=settings.query_model or settings.model,
            max_tokens=QUERY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=SearchQuery,
        )
    except ValidationError:
        return ticket_text_instead(ticket, "invalid output")

    if output.parsed_output is None:
        return ticket_text_instead(ticket, f"stop_reason={output.stop_reason}")

    query = output.parsed_output.query.strip()
    if not query:
        return ticket_text_instead(ticket, "empty query")

    return query


def ticket_text_instead(ticket: Ticket, reason: str) -> str:
    safe_log.warning(
        "Ticket %s: no usable search query (%s), searching the ticket text",
        ticket.id,
        reason,
    )
    return ticket.text
