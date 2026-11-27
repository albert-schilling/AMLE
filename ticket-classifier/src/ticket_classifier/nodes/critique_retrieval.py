from ..config import get_settings
from ..models import TriageState, TriageUpdate
from ..telemetry import get_loggers

logger, safe_log = get_loggers(__name__)


class MissingResultError(RuntimeError):
    """There is no search result to judge: ``retrieve_knowledge`` did not run first."""


def node_critique_retrieval(state: TriageState) -> TriageUpdate:
    """Judge the latest search: ok if a passage passed the minimum score.

    Only the score, no model call: this check decides whether to pay for a reword.
    """
    retrieval = state["retrieval"]
    if retrieval.result is None:
        raise MissingResultError("critique_retrieval needs a search result")
    judged = retrieval.judged(retrieval.result.has_sources)
    max_attempts = get_settings().knowledge_max_attempts

    if judged.ok:
        verdict = "ok"
    elif judged.can_reword(max_attempts):
        verdict = "weak, rewording the query"
    else:
        verdict = "weak, attempts spent: the reply goes on without sources"
    best = retrieval.result.best_found_score
    safe_log.info(
        "Ticket %s attempt %d of %d: best found score %s, %s",
        state["ticket"].id,
        judged.attempts,
        max_attempts,
        "none" if best is None else f"{best:.3f}",
        verdict,
    )
    return {"retrieval": judged}
