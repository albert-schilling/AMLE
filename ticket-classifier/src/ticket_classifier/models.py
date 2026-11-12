from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

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


class Resolved(BaseModel):
    """Triage ended with a classification and no escalation."""

    escalated: Literal[False] = False
    classification: TicketClassification


class Escalated(BaseModel):
    """Triage ended with a human takeover; a classification may still exist."""

    escalated: Literal[True] = True
    escalation_reason: str
    classification: TicketClassification | None = None


# Tagged union on ``escalated``: impossible states cannot be built or loaded.
TriageResult = Annotated[Resolved | Escalated, Field(discriminator="escalated")]


class ResolvedTicket(BaseModel):
    ticket_id: str
    customer_id: str | None = None
    category: Category
    priority: Priority
    escalated: Literal[False] = False
    escalation_reason: None = None


class EscalatedTicket(BaseModel):
    ticket_id: str
    customer_id: str | None = None
    category: Category | None = None  # absent when escalated without a classification
    priority: Priority | None = None
    escalated: Literal[True] = True
    escalation_reason: str


ClassifiedTicket = Annotated[
    ResolvedTicket | EscalatedTicket, Field(discriminator="escalated")
]


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
