"""What comes out: one result row per finished ticket, saved to results.json."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .domain import Category, Priority


class TicketResult(BaseModel):
    """Fields every result row has."""

    ticket_id: str
    customer_id: str | None = None
    category: Category
    priority: Priority


class ResolvedTicket(TicketResult):
    """Handled without a human takeover."""

    escalated: Literal[False] = False
    escalation_reason: None = None


class EscalatedTicket(TicketResult):
    """A human took over."""

    escalated: Literal[True] = True
    escalation_reason: str


# Tagged union on ``escalated``: impossible states cannot be built or loaded.
ClassifiedTicket = Annotated[
    ResolvedTicket | EscalatedTicket, Field(discriminator="escalated")
]
