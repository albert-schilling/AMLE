from langgraph.runtime import Runtime

from ..config import get_settings
from ..context import WorkflowContext, require_context
from ..models import RetrievalResult, RetrievalStepError, TriageState, TriageUpdate
from ..telemetry import get_loggers
from .names import RETRIEVE_KNOWLEDGE

logger, safe_log = get_loggers(__name__)


def node_retrieve_knowledge(
    state: TriageState, runtime: Runtime[WorkflowContext]
) -> TriageUpdate:
    """Search the policy passages closest in meaning to the latest query, split at
    the minimum score."""
    context = require_context(runtime, RETRIEVE_KNOWLEDGE)
    ticket = state["ticket"]
    retrieval = state["retrieval"]
    if retrieval.query is None:
        raise RetrievalStepError(
            f"{RETRIEVE_KNOWLEDGE} needs a query from formulate_query"
        )
    settings = get_settings()

    found = context.knowledge.search(retrieval.query, settings.knowledge_top_k)
    result = RetrievalResult.split(found, settings.knowledge_min_score)

    safe_log.info(
        "Ticket %s: %d policy passages, %d below the minimum score: %s",
        ticket.id,
        len(result.passages),
        result.dropped,
        ", ".join(f"{p.citation} {p.score:.3f}" for p in found),
    )
    return {"retrieval": retrieval.with_result(result)}
