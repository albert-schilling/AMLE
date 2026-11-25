from langgraph.types import StreamWriter

from ..client import get_client
from ..config import get_settings
from ..models import TriageState, TriageUpdate
from ..prompts import REPLY_SYSTEM_PROMPT, reply_content
from ..replies import build_reply
from ..telemetry import get_loggers
from .triage import ignore_event

logger, safe_log = get_loggers(__name__)


def node_draft_reply(
    state: TriageState, writer: StreamWriter = ignore_event
) -> TriageUpdate:
    """Draft a reply from the policy passages, with citations from the API.

    A separate call from triage: citations do not work with structured outputs.
    Raises ``ReplyError`` if the model gives no usable reply.
    """
    settings = get_settings()
    ticket = state["ticket"]
    passages = state["retrieval"].passages
    model = settings.reply_model or settings.model

    writer({"event": "drafting reply", "ticket_id": ticket.id, "model": model})

    message = get_client().messages.create(
        model=model,
        max_tokens=settings.reply_max_tokens,
        system=REPLY_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": reply_content(
                    ticket, state["customer"], state["classification"], passages
                ),
            }
        ],
    )
    reply = build_reply(message, passages)

    safe_log.info(
        "Ticket %s reply drafted, citations=%d sources=%s",
        ticket.id,
        len(reply.citations),
        ", ".join(c.citation for c in reply.citations) or "none",
    )
    return {"reply": reply}
