"""What the CLI subcommands do: run the workflow over tickets, answer a paused one,
index the knowledge base, compare chunk settings."""

from collections.abc import Sequence

from .checkpoint import open_checkpointer
from .config import Settings
from .context import WorkflowContext
from .graph import build_workflow, write_mermaid
from .knowledge import (
    BuildResult,
    KnowledgeEvaluation,
    compare_chunk_settings,
    compare_thresholds,
    load_documents,
    load_questions,
    open_knowledge_base,
)
from .models import ClassifiedTicket, HumanAnswer, Ticket
from .queries import write_query
from .runner import BatchResult, resume_ticket, run_all, to_classified_ticket
from .storage import merge_results, save_results
from .telemetry import get_loggers, ticket_span

logger, safe_log = get_loggers(__name__)


class MissingApiKeyError(RuntimeError):
    """``run`` needs ``ANTHROPIC_API_KEY`` for triage, and it is not set."""


def run(tickets: list[Ticket], settings: Settings) -> BatchResult:
    """Classify all tickets and save the results; high-priority ones stay paused.

    Fails before the first ticket, so no API call is made, if the API key is not set
    (``MissingApiKeyError``) or the knowledge base is not ready: database not set or
    down, model not downloaded, index not built.
    """
    if settings.anthropic_api_key is None:
        raise MissingApiKeyError("ANTHROPIC_API_KEY is not set; run needs it")

    with open_knowledge_base(settings) as knowledge:
        knowledge.require_index()

        with open_checkpointer(settings.checkpoint_path) as checkpointer:
            workflow = build_workflow(checkpointer)
            write_mermaid(workflow, settings.graph_path)

            context = WorkflowContext(knowledge=knowledge, write_query=write_query)

            batch = run_all(tickets, workflow=workflow, context=context)

    save_results(batch.classified, settings.results_path)
    safe_log.info(
        "Of %d tickets: %d classified, %d paused, %d failed.",
        len(tickets),
        len(batch.classified),
        len(batch.paused),
        len(batch.failed),
    )
    logger.info("Results in %s", settings.results_path)
    for ticket_id in batch.paused:
        logger.info(
            "Ticket %s waits for a human. Answer with: "
            "ticket-classifier resume %s --approve|--decline --note TEXT",
            ticket_id,
            ticket_id,
        )
    return batch


def resume(
    ticket_id: str, answer: HumanAnswer, settings: Settings
) -> ClassifiedTicket | None:
    """Answer a paused ticket, finish its run and add the result to the saved ones.

    Returns None if the run pauses again. Raises ``NotPausedError`` if the ticket has
    no paused run.
    """
    with ticket_span(ticket_id, "resume"):
        with open_checkpointer(settings.checkpoint_path) as checkpointer:
            workflow = build_workflow(checkpointer)
            result = resume_ticket(workflow, ticket_id, answer)

        if result is None:
            safe_log.info("Ticket %s is paused again", ticket_id)
            return None

        classified = to_classified_ticket(result)
        merge_results([classified], settings.results_path)
        safe_log.info("Ticket %s done", ticket_id)
        logger.info("Results in %s", settings.results_path)
        return classified


def index_knowledge(settings: Settings) -> BuildResult:
    """Embed the knowledge base into PostgreSQL, unless it is unchanged.

    The only command that may download the embedding model.
    """
    docs = load_documents(settings.knowledge_base_path)

    with open_knowledge_base(settings, download=True) as knowledge:
        result = knowledge.build(docs)

    safe_log.info(
        "Knowledge index %d (%s, size %d, overlap %d): %d chunks from %d documents, %s",
        result.index_id,
        settings.embedding_model,
        settings.chunk_size,
        settings.chunk_overlap,
        result.chunk_count,
        len(docs),
        "unchanged" if result.reused else "rebuilt",
    )
    return result


def evaluate_knowledge(
    settings: Settings,
    chunk_settings: Sequence[tuple[int, int]],
    thresholds: Sequence[float],
) -> KnowledgeEvaluation:
    """Search the labelled questions with an index per (size, overlap), and compare
    minimum scores on the configured chunk setting.

    Builds missing indexes with the local model; changes nothing for ``run``, which
    keeps using the chunk setting from the settings.
    """
    docs = load_documents(settings.knowledge_base_path)
    questions = load_questions(settings.knowledge_questions_path)

    with open_knowledge_base(settings) as knowledge:
        results = compare_chunk_settings(knowledge, docs, questions, chunk_settings)
        knowledge.build(docs)  # the configured index; skipped if unchanged
        threshold_results = compare_thresholds(knowledge.search, questions, thresholds)

    for result in results:
        safe_log.info(
            "Chunk size %d, overlap %d: %d chunks, MRR vector %.2f, keyword %.2f",
            result.chunk_size,
            result.chunk_overlap,
            result.chunk_count,
            result.vector.mean_reciprocal_rank,
            result.keyword.mean_reciprocal_rank,
        )
    for threshold in threshold_results:
        safe_log.info(
            "Min score %.2f: answer kept %.2f, answerable without passage %.2f, "
            "unanswerable without passage %.2f",
            threshold.min_score,
            threshold.answer_kept,
            threshold.answerable_unsourced,
            threshold.unanswerable_unsourced,
        )
    return KnowledgeEvaluation(results, threshold_results)
