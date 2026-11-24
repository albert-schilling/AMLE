from langgraph.runtime import Runtime

from ..config import get_settings
from ..context import WorkflowContext
from ..models import TriageState
from ..telemetry import get_loggers

logger, safe_log = get_loggers(__name__)


class MissingContextError(RuntimeError):
    """The run was started without a ``WorkflowContext``."""


def node_retrieve_knowledge(
    state: TriageState, runtime: Runtime[WorkflowContext]
) -> TriageState:
    """Find the policy passages closest in meaning to the ticket text, leaving out
    those too weak to help."""

    if runtime.context is None:
        raise MissingContextError("retrieve_knowledge needs a WorkflowContext")

    ticket = state["ticket"]
    settings = get_settings()

    found = runtime.context.knowledge.search(ticket.text, settings.knowledge_top_k)
    passages = [p for p in found if p.score >= settings.knowledge_min_score]

    safe_log.info(
        "Ticket %s: %d policy passages, %d below the minimum score: %s",
        ticket.id,
        len(passages),
        len(found) - len(passages),
        ", ".join(f"{p.citation} {p.score:.3f}" for p in found),
    )
    return {"knowledge": passages}
