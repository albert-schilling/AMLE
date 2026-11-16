from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from langchain_protocol import TypedDict
from pydantic import BaseModel, ConfigDict, Field

Category = Literal["billing", "technical", "account", "other"]
Priority = Literal["low", "medium", "high"]


class Ticket(BaseModel):
    id: str
    customer_id: str | None = None
    text: str


class TicketClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority


class ResolvedTicket(BaseModel):
    """Triage ended with a classification and no escalation."""

    ticket_id: str
    customer_id: str | None = None
    category: Category
    priority: Priority
    escalated: Literal[False] = False
    escalation_reason: None = None


class EscalatedTicket(BaseModel):
    """Triage ended with a human takeover; a classification may still exist."""

    ticket_id: str
    customer_id: str | None = None
    category: Category | None = None  # absent when escalated without a classification
    priority: Priority | None = None
    escalated: Literal[True] = True
    escalation_reason: str


# Tagged union on ``escalated``: impossible states cannot be built or loaded.
ClassifiedTicket = Annotated[
    ResolvedTicket | EscalatedTicket, Field(discriminator="escalated")
]


class NotEscalated(BaseModel):
    escalated: Literal[False] = False


class Escalated(BaseModel):
    escalated: Literal[True] = True
    escalation_reason: str


Escalation = Annotated[NotEscalated | Escalated, Field(discriminator="escalated")]

Product = Literal["Wendel", "Pip", "Brio"]


class Customer(BaseModel):
    """Basic customer information with a list of purchased products."""

    id: str
    first_name: str
    last_name: str
    email: str
    account_age_days: int
    past_refunds_90d: int
    plan: Literal["free", "pro"]
    products: list[Product]


class Payment(BaseModel):
    """One row of the (fake) payments file served on GitHub Pages."""

    client_id: str
    invoice_number: str
    amount: Decimal
    timestamp: datetime


def combine_responses(left: list[str], right: list[str]) -> list[str]:
    """left and right are lists of outputs from previous nodes"""
    return left + right


class TriageState(TypedDict, total=False):
    classification: TicketClassification | None
    """The classification assigned to this ticket."""
    escalation: Escalation = NotEscalated()
    """The escalation status of this ticket."""
    customer: Customer | None
    """The customer associated with this ticket."""
    last_updated_by: str | None
    """The identifier of the last node that updated this state."""
    responses: Annotated[list[str], combine_responses] = []
    """List of responses accumulated across nodes."""
    ticket: Ticket
    """The ticket being processed in this run."""
