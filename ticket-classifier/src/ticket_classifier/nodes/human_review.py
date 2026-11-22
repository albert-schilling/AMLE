import logging

from langgraph.types import interrupt

from ..models import (
    Escalated,
    EscalationRequest,
    HumanAnswer,
    NotEscalated,
    TriageState,
)
from ..telemetry import CONSOLE_ONLY

logger = logging.getLogger(__name__)


def escalation_request(state: TriageState) -> EscalationRequest:
    """What a person needs to decide whether to take over the ticket."""
    return {
        "question": "High priority ticket. Should a human take over?",
        "answer_format": {"approved": "bool", "note": "str"},
        "ticket": state["ticket"],
        "customer": state["customer"],
        "classification": state["classification"],
    }


def node_human_review(state: TriageState) -> TriageState:
    """Pause the run until a person answers with a ``HumanAnswer``."""
    # Runs again on resume: everything above interrupt() must be safe to repeat.
    answer: HumanAnswer = interrupt(escalation_request(state))
    logger.info(
        "Ticket %s human answer: %r", state["ticket"].id, answer, extra=CONSOLE_ONLY
    )

    if answer["approved"]:
        reason = answer["note"] or "High priority ticket"
        return {"escalation": Escalated(escalation_reason=reason)}
    return {"escalation": NotEscalated()}
