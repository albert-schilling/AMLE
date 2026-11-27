"""What comes out: one result row per finished ticket, saved to results.json."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .domain import Category, Priority
from .reply import Reply


class TicketResult(BaseModel):
    """Fields every result row has."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    ticket_id: str
    customer_id: str | None = None
    category: Category
    priority: Priority
    reply: Reply
    """Draft for a person to send, with its cited sources."""


class ResolvedTicket(TicketResult):
    """Handled without a human takeover."""

    escalated: Literal[False] = False
    escalation_reason: None = None


class EscalatedTicket(TicketResult):
    """A human took over."""

    escalated: Literal[True] = True
    escalation_reason: str


ClassifiedTicket = Annotated[
    ResolvedTicket | EscalatedTicket, Field(discriminator="escalated")
]
"""Tagged union on ``escalated``: impossible states cannot be built or loaded."""
