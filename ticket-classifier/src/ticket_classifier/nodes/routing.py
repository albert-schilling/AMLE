from typing import Literal

from ..config import get_settings
from ..models import TriageState
from .names import HUMAN_REVIEW, MARK_HANDLED, REFORMULATE, RETRIEVAL_DONE


def route_by_priority(state: TriageState) -> Literal["human_review", "mark_handled"]:
    """High priority goes to a human, everything else is handled automatically.

    Returns node names: LangGraph reads the possible targets from the ``Literal``
    return type, so no path map is needed.
    """
    if state["classification"].priority == "high":
        return HUMAN_REVIEW
    return MARK_HANDLED


def route_after_critique(
    state: TriageState,
) -> Literal["reformulate", "retrieval_done"]:
    """Search again with a new query while the result is weak and attempts are left.

    The only way back in the graph; ``KNOWLEDGE_MAX_ATTEMPTS`` bounds it. Returns
    labels, not node names: ``graph.py`` maps them, and the diagram shows them on
    the edges.
    """

    can_reword = state["retrieval"].can_reword(get_settings().knowledge_max_attempts)

    if can_reword:
        return REFORMULATE
    return RETRIEVAL_DONE
