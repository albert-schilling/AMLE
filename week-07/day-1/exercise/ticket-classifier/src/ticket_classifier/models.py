from typing import Literal

from pydantic import BaseModel, ConfigDict

Category = Literal["billing", "technical", "account", "other"]
Priority = Literal["low", "medium", "high"]


class Ticket(BaseModel):
    id: str
    text: str


class TicketClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
