"""The structured-output contract for ScoutBot's triage step.

Enums (not free strings) for category/priority so a malformed value fails validation loudly,
instead of silently becoming whatever the model felt like writing.
"""
from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    billing = "billing"
    technical = "technical"
    account = "account"
    other = "other"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class QueryRoute(str, Enum):
    """How much retrieval a ticket needs - Day 4's adaptive-RAG decision.

    Not every ticket deserves the same effort. Yesterday every ticket entered the full re-query
    loop, whether it was a genuine policy question or a "thanks, that's all!". Today a router picks
    one of three strategies up front, and the graph takes a different path for each:

    - `direct`: no retrieval at all. A greeting, a thank-you, an acknowledgement - courtesy answers
      it, and searching a policy corpus for it is wasted latency and a wasted model call.
    - `retrieve`: a single search. A clear, single-topic policy question ("how long do refunds
      take?") that one good retrieval answers, with no need to reword and try again.
    - `iterative`: Day 3's full bounded loop. Anything vague, multi-part, oblique, or
      account-specific, where the first search might miss and the agent should get to reword.

    A `str` enum, like `Category` and `Priority`, so the value stored in state is a plain string the
    checkpointer serialises and a router can compare without importing this class. `iterative` is the
    safe default when the router is unsure: erring toward *more* retrieval never invents an answer,
    where erring toward `direct` is exactly the ungrounded guess the whole week is built to avoid.
    """

    direct = "direct"
    retrieve = "retrieve"
    iterative = "iterative"


class TicketTriage(BaseModel):
    """The validated result ScoutBot must produce for every ticket."""

    category: Category
    priority: Priority
    suggested_owner: str = Field(
        description="Team or person who should handle this ticket, e.g. 'billing-team'."
    )
