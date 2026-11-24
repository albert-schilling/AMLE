"""Node names as they appear in the graph, the trace and ``StateSnapshot.next``."""

from typing import Final

# Final: type checkers see each name as its Literal, e.g. for route_after_triage.
GET_CUSTOMER: Final = "get_customer"
RETRIEVE_KNOWLEDGE: Final = "retrieve_knowledge"
TRIAGE: Final = "triage"
HUMAN_REVIEW: Final = "human_review"
MARK_HANDLED: Final = "mark_handled"
