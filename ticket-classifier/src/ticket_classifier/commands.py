"""What the CLI subcommands do: run the workflow over tickets, answer a paused one."""

import logging

from .checkpoint import open_checkpointer
from .config import Settings
from .graph import build_workflow, write_mermaid
from .models import ClassifiedTicket, HumanAnswer, Ticket
from .runner import BatchResult, resume_ticket, run_all, to_classified_ticket
from .storage import merge_results, save_results
from .telemetry import ticket_span

logger = logging.getLogger(__name__)


class MissingApiKeyError(RuntimeError):
    """``run`` needs ``ANTHROPIC_API_KEY`` for triage, and it is not set."""


def run(tickets: list[Ticket], settings: Settings) -> BatchResult:
    """Classify all tickets and save the results; high-priority ones stay paused.

    Raises ``MissingApiKeyError`` before any work if the API key is not set.
    """
    if settings.anthropic_api_key is None:
        raise MissingApiKeyError("ANTHROPIC_API_KEY is not set; run needs it")

    with open_checkpointer(settings.checkpoint_path) as checkpointer:
        workflow = build_workflow(checkpointer)
        write_mermaid(workflow, settings.graph_path)
        batch = run_all(tickets, workflow=workflow)

    save_results(batch.classified, settings.results_path)
    logger.info(
        "Of %d tickets: %d classified, %d paused, %d failed. Results in %s",
        len(tickets),
        len(batch.classified),
        len(batch.paused),
        len(batch.failed),
        settings.results_path,
    )
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
            logger.info("Ticket %s is paused again", ticket_id)
            return None

        classified = to_classified_ticket(result)
        merge_results([classified], settings.results_path)
        logger.info("Ticket %s done, results in %s", ticket_id, settings.results_path)
        return classified
