from ..config import get_settings
from ..models import TriageState, TriageUpdate
from ..telemetry import get_loggers
from .routing import attempts_spent

logger, safe_log = get_loggers(__name__)


class MissingResultError(RuntimeError):
    """There is no search result to judge: ``retrieve_knowledge`` did not run first."""


def node_critique_retrieval(state: TriageState) -> TriageUpdate:
    """Judge the latest search: ok if a passage passed the minimum score.

    Only the score, no model call: this check decides whether to pay for a reword.
    """
    search = state["search"]
    if search.result is None:
        raise MissingResultError("critique_retrieval needs a search result")
    ok = search.result.has_sources

    if ok:
        verdict = "ok"
    elif attempts_spent(search):
        verdict = "weak, attempts spent: the reply goes on without sources"
    else:
        verdict = "weak, rewording the query"
    best = search.result.best_score
    safe_log.info(
        "Ticket %s search %d of %d: best score %s, %s",
        state["ticket"].id,
        search.attempts,
        get_settings().knowledge_max_attempts,
        "none" if best is None else f"{best:.3f}",
        verdict,
    )
    return {"search": search.judged(ok)}
