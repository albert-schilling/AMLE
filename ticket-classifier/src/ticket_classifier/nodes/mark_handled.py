from ..models import NotEscalated, TriageState


def node_mark_handled(state: TriageState) -> TriageState:
    """Record that the ticket was handled automatically, with no human."""
    return {"escalation": NotEscalated()}
