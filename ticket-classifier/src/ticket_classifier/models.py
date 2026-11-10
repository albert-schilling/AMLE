from typing import Literal

from pydantic import BaseModel, ConfigDict

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


class ClassifiedTicket(BaseModel):
    ticket_id: str
    customer_id: str | None = None
    category: Category
    priority: Priority


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
