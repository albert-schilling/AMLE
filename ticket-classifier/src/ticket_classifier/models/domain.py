"""What comes in: tickets, customers, and the classification the model returns."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Category = Literal["billing", "technical", "account", "other"]
Priority = Literal["low", "medium", "high"]
Product = Literal["Wendel", "Pip", "Brio"]


class Ticket(BaseModel):
    """A support ticket as it comes in."""

    id: str
    customer_id: str | None = None
    text: str


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


class TicketClassification(BaseModel):
    """The model's structured output."""

    # No extra fields: the JSON schema sent to the model forbids them too.
    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
