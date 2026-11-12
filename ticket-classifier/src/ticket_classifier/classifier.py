import logging
from collections.abc import Callable

from anthropic import Anthropic

from .config import get_settings
from .models import Escalated, Resolved, Ticket, TicketClassification
from .prompts import SYSTEM_PROMPT, create_prompt
from .tools import (
    Escalation,
    lookup_customer,
    make_escalation_tool,
    make_web_fetch_tool,
)
from .trace import log_actions, log_final, log_observations

logger = logging.getLogger(__name__)


class ClassificationError(RuntimeError):
    """The model did not return a usable classification."""


def create_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key.get_secret_value())


def classify(
    ticket: Ticket, client: Anthropic, approve: Callable[[str], bool]
) -> Resolved | Escalated:
    """Run the agent loop for one ticket and log its reasoning trace.

    The loop (reason, call a tool, observe, repeat) is capped at ``max_iterations``;
    hitting the cap counts as an automatic escalation. ``approve`` is the human
    gate for ``escalate_to_human``.
    """
    settings = get_settings()
    escalation = Escalation(approve)

    logger.info("Classifying ticket %s", ticket.id)

    # Manual extended thinking (budget_tokens) is a legacy mode: it works on Haiku 4.5
    # but models from Claude 4.7 on reject it with a 400 and need adaptive thinking
    # ({"type": "adaptive"} plus an effort level) instead. Haiku 4.5 does not think
    # between tool calls (no interleaved thinking), so thinking appears at step 1 only.
    # temperature/top_p/top_k cannot be set: API version 2026-10-21 rejects them.
    thinking: dict = (
        {"thinking": {"type": "enabled", "budget_tokens": settings.thinking_budget}}
        if settings.thinking_budget
        else {}
    )

    runner = client.beta.messages.tool_runner(
        model=settings.model,
        max_iterations=settings.max_iterations,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": create_prompt(ticket)}],
        tools=[
            lookup_customer,
            make_escalation_tool(escalation),
            make_web_fetch_tool(),
        ],
        # one tool call per turn: an escalation must see the lookup result first
        tool_choice={"type": "auto", "disable_parallel_tool_use": True},
        output_format=TicketClassification,
        **thinking,
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
        return Escalated(escalation_reason=reason)

    if final.parsed_output is None:
        raise ClassificationError(
            f"No parsed classification for ticket {ticket.id} "
            f"(stop_reason={final.stop_reason})"
        )

    result: Resolved | Escalated
    if escalation.reason is not None:
        result = Escalated(
            escalation_reason=escalation.reason, classification=final.parsed_output
        )
    else:
        result = Resolved(classification=final.parsed_output)
    log_final(ticket.id, f"{final.parsed_output}, escalated={result.escalated}")
    return result
