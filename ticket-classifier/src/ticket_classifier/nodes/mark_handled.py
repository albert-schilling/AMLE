from ..models import NotEscalated, TriageState, TriageUpdate


def node_mark_handled(state: TriageState) -> TriageUpdate:
    """Record that the ticket was handled automatically, with no human."""
    return {"escalation": NotEscalated()}
