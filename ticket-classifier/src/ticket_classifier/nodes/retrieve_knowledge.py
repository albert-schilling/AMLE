from langgraph.runtime import Runtime

from ..config import get_settings
from ..context import WorkflowContext, require_context
from ..models import RetrievalResult, TriageState, TriageUpdate
from ..telemetry import get_loggers
from .names import RETRIEVE_KNOWLEDGE

logger, safe_log = get_loggers(__name__)


class MissingQueryError(RuntimeError):
    """The search has no query: ``formulate_query`` did not run first."""


def node_retrieve_knowledge(
    state: TriageState, runtime: Runtime[WorkflowContext]
) -> TriageUpdate:
    """Search the policy passages closest in meaning to the latest query, split at
    the minimum score."""
    context = require_context(runtime, RETRIEVE_KNOWLEDGE)
    ticket = state["ticket"]
    search = state["search"]
    if search.query is None:
        raise MissingQueryError(f"{RETRIEVE_KNOWLEDGE} needs a search query")
    settings = get_settings()

    found = context.knowledge.search(search.query, settings.knowledge_top_k)
    result = RetrievalResult.split(found, settings.knowledge_min_score)

    safe_log.info(
        "Ticket %s: %d policy passages, %d below the minimum score: %s",
        ticket.id,
        len(result.passages),
        result.dropped,
        ", ".join(f"{p.citation} {p.score:.3f}" for p in found),
    )
    return {"search": search.with_result(result)}
