from typing import Literal

from ..models import TriageState
from .names import HUMAN_REVIEW, MARK_HANDLED


def route_after_triage(state: TriageState) -> Literal["human_review", "mark_handled"]:
    """High priority goes to a human, everything else is handled automatically.

    LangGraph reads the possible targets from the ``Literal`` return type.
    """
    if state["classification"].priority == "high":
        return HUMAN_REVIEW
    return MARK_HANDLED
