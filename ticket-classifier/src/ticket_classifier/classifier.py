import logging
from collections.abc import Callable

from anthropic import Anthropic

from .config import get_settings
from .models import Ticket, TicketClassification, TriageResult
from .prompts import SYSTEM_PROMPT, create_prompt
from .tools import Escalation, lookup_customer, make_escalation_tool
from .trace import log_actions, log_final, log_observations

logger = logging.getLogger(__name__)


class ClassificationError(RuntimeError):
    """The model did not return a usable classification."""


def create_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key.get_secret_value())


def classify(
    ticket: Ticket, client: Anthropic, approve: Callable[[str], bool]
) -> TriageResult:
    """Run the agent loop for one ticket and log its reasoning trace.

    The loop (reason, call a tool, observe, repeat) is capped at ``max_iterations``;
    hitting the cap counts as an automatic escalation. ``approve`` is the human
    gate for ``escalate_to_human``.
    """
    settings = get_settings()
    escalation = Escalation(approve)

    logger.info("Classifying ticket %s", ticket.id)

    runner = client.beta.messages.tool_runner(
        model=settings.model,
        max_iterations=settings.max_iterations,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": create_prompt(ticket)}],
        tools=[lookup_customer, make_escalation_tool(escalation)],
        output_format=TicketClassification,
    )

    for step, message in enumerate(runner, start=1):
        log_actions(ticket.id, step, message)  # before tools run (and may prompt)
        # the runner caches this response, so tools run once
        log_observations(ticket.id, step, runner.generate_tool_call_response())

    final = runner.until_done()
    logger.debug("Ticket %s finished, stop_reason=%s", ticket.id, final.stop_reason)

    if final.stop_reason == "tool_use":  # the model still wanted tools: cap reached
        reason = f"Iteration cap reached ({settings.max_iterations} steps)"
        log_final(ticket.id, f"ESCALATED automatically - {reason}")
        return TriageResult(escalated=True, escalation_reason=reason)

    if final.parsed_output is None:
        raise ClassificationError(
            f"No parsed classification for ticket {ticket.id} "
            f"(stop_reason={final.stop_reason})"
        )

    escalated = escalation.reason is not None
    result = TriageResult(
        classification=final.parsed_output,
        escalated=escalated,
        escalation_reason=escalation.reason,
    )
    log_final(ticket.id, f"{final.parsed_output}, escalated={escalated}")
    return result
