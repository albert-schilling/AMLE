"""What the graph carries and saves in checkpoints."""

from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field

from .domain import Customer, Ticket, TicketClassification
from .knowledge import KnowledgePassage


class NotEscalated(BaseModel):
    escalated: Literal[False] = False


class Escalated(BaseModel):
    escalated: Literal[True] = True
    escalation_reason: str


Escalation = Annotated[NotEscalated | Escalated, Field(discriminator="escalated")]


class TriageState(TypedDict):
    """One ticket's run. Only ``ticket`` is given at the start; nodes add the rest.

    A TypedDict has no defaults: a key that no node has written yet is missing.
    """

    ticket: Ticket
    customer: NotRequired[Customer | None]  # None: no id, unknown, or unreadable
    # Policy passages for the ticket, best first.
    knowledge: NotRequired[list[KnowledgePassage]]
    classification: NotRequired[TicketClassification]
    escalation: NotRequired[Escalation]


class EscalationRequest(TypedDict):
    """What a paused ticket shows the reviewer: the value passed to ``interrupt()``."""

    question: str
    answer_format: dict[str, str]
    ticket: Ticket
    customer: Customer | None
    classification: TicketClassification
    policies: list[KnowledgePassage]  # the passages triage saw, best first


class HumanAnswer(TypedDict):
    """A person's answer to a paused ticket: the return value of ``interrupt()``."""

    approved: bool  # True: a human takes over the ticket
    note: str
