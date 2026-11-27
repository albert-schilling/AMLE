from langgraph.runtime import Runtime

from ..context import WorkflowContext, require_context
from ..models import TriageState, TriageUpdate
from ..telemetry import get_loggers
from .names import FORMULATE_QUERY

logger, safe_log = get_loggers(__name__)


def node_formulate_query(
    state: TriageState, runtime: Runtime[WorkflowContext]
) -> TriageUpdate:
    """Write the next search query. After a weak search, the writer sees the queries
    that failed and the passages the last one found, so it can move away from them."""
    context = require_context(runtime, FORMULATE_QUERY)
    ticket = state["ticket"]
    retrieval = state["retrieval"]

    query = context.write_query(ticket, retrieval)

    # The query can quote the ticket: it stays on the console. critique_retrieval
    # sends the exported line of this attempt.
    logger.info(
        "Ticket %s attempt %d query: %r", ticket.id, retrieval.attempts + 1, query
    )
    return {"retrieval": retrieval.with_query(query)}
