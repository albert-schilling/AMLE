from langgraph.types import interrupt

from ..models import (
    Escalated,
    EscalationRequest,
    HumanAnswer,
    NotEscalated,
    TriageState,
    TriageUpdate,
)
from ..telemetry import get_loggers

logger, safe_log = get_loggers(__name__)


def escalation_request(state: TriageState) -> EscalationRequest:
    """What a person needs to decide whether to take over the ticket."""
    return {
        "question": "High priority ticket. Should a human take over?",
        "answer_format": {"approved": "bool", "note": "str"},
        "ticket": state["ticket"],
        "customer": state["customer"],
        "classification": state["classification"],
        "policies": list(state["retrieval"].passages),
        "reply": state["reply"],
    }


def node_human_review(state: TriageState) -> TriageUpdate:
    """Pause the run until a person answers with a ``HumanAnswer``."""
    # Runs again on resume: everything above interrupt() must be safe to repeat.
    answer: HumanAnswer = interrupt(escalation_request(state))
    ticket_id = state["ticket"].id
    safe_log.info("Ticket %s human answer: approved=%s", ticket_id, answer["approved"])
    logger.info("Ticket %s human note: %r", ticket_id, answer["note"])

    if answer["approved"]:
        reason = answer["note"] or "High priority ticket"
        return {"escalation": Escalated(escalation_reason=reason)}
    return {"escalation": NotEscalated()}
