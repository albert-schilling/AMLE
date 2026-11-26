"""The graph's names: node names, as they appear in the graph, the trace and
``StateSnapshot.next``, and the edge labels of routers that return labels."""

from typing import Final

# Final: type checkers see each name as its Literal, e.g. for route_by_priority.
GET_CUSTOMER: Final = "get_customer"
FORMULATE_QUERY: Final = "formulate_query"
RETRIEVE_KNOWLEDGE: Final = "retrieve_knowledge"
CRITIQUE_RETRIEVAL: Final = "critique_retrieval"
TRIAGE: Final = "triage"
DRAFT_REPLY: Final = "draft_reply"
HUMAN_REVIEW: Final = "human_review"
MARK_HANDLED: Final = "mark_handled"

# Edge labels of route_after_critique; graph.py maps them to nodes.
REFORMULATE: Final = "reformulate"
RETRIEVAL_DONE: Final = "retrieval_done"
