import logging
import time
from collections.abc import Callable
from typing import Any

from anthropic import Anthropic

from .config import Settings, get_settings
from .models import (
    ClassifiedTicket,
    EscalatedTicket,
    ResolvedTicket,
    Ticket,
    TicketClassification,
)
from .prompts import SYSTEM_PROMPT, create_prompt
from .tools import (
    CODE_EXECUTION_TOOL,
    Escalation,
    find_duplicate_charges,
    lookup_customer,
    make_escalation_tool,
    make_fetch_tool,
)
from .trace import (
    LoopStats,
    append_jsonl,
    final_record,
    log_actions,
    log_final,
    log_observations,
    step_record,
)

logger = logging.getLogger(__name__)


class ClassificationError(RuntimeError):
    """The model did not return a usable classification."""


def user_content(ticket: Ticket, log_file_id: str | None) -> str | list[dict]:
    """The user message: plain text, or text plus a file for the code sandbox."""
    prompt = create_prompt(ticket)
    if log_file_id is None:
        return prompt
    return [
        {"type": "text", "text": f"{prompt}\nAttached log file: {log_file_id}"},
        {"type": "container_upload", "file_id": log_file_id},
    ]


def build_runner(
    client: Anthropic,
    ticket: Ticket,
    escalation: Escalation,
    log_file_id: str | None,
    settings: Settings,
) -> Any:
    """The SDK tool runner for one ticket, with all tools and options set."""
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
    return client.beta.messages.tool_runner(
        model=settings.model,
        max_iterations=settings.max_iterations,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content(ticket, log_file_id)}],
        tools=[
            lookup_customer,
            make_escalation_tool(escalation),
            make_fetch_tool(),
            find_duplicate_charges,
            CODE_EXECUTION_TOOL,
        ],
        # one tool call per turn: an escalation must see the lookup result first
        tool_choice={"type": "auto", "disable_parallel_tool_use": True},
        output_format=TicketClassification,
        **thinking,
    )


def run_loop(runner: Any, ticket_id: str, settings: Settings) -> tuple[Any, LoopStats]:
    """Drive the runner to the end; log and record every step.

    Returns the final message and the totals of the run.
    """
    stats = LoopStats()
    started = time.perf_counter()  # a step = model call + tool run (incl. approval)
    for step, message in enumerate(runner, start=1):
        log_actions(ticket_id, step, message)  # before tools run (and may prompt)
        # the runner caches this response, so tools run once
        observation = runner.generate_tool_call_response()
        log_observations(ticket_id, step, observation)
        duration_ms = round((time.perf_counter() - started) * 1000)
        record = step_record(
            ticket_id, step, settings.model, message, observation, duration_ms
        )
        stats.add_step(message.usage, record["container_ms_estimate"])
        append_jsonl(settings.trace_file, record)
        started = time.perf_counter()
    return runner.until_done(), stats


def to_result(
    final: Any, escalation: Escalation, ticket: Ticket, max_iterations: int
) -> ClassifiedTicket:
    """Turn the final message into the ticket's result row.

    The model still wanting tools means the cap was hit: an automatic escalation
    without a classification. Raises ``ClassificationError`` if nothing was parsed.
    """
    ids = {"ticket_id": ticket.id, "customer_id": ticket.customer_id}
    if final.stop_reason == "tool_use":
        return EscalatedTicket(
            **ids, escalation_reason=f"Iteration cap reached ({max_iterations} steps)"
        )
    if final.parsed_output is None:
        raise ClassificationError(
            f"No parsed classification for ticket {ticket.id} "
            f"(stop_reason={final.stop_reason})"
        )
    classification = final.parsed_output.model_dump()
    if escalation.reason is not None:
        return EscalatedTicket(
            **ids, **classification, escalation_reason=escalation.reason
        )
    return ResolvedTicket(**ids, **classification)


def summarize(result: ClassifiedTicket, stats: LoopStats) -> str:
    """One line for the trace log: the outcome plus token and container totals."""
    totals = (
        f"tokens in/out={stats.input_tokens}/{stats.output_tokens}, "
        f"container<={stats.container_ms}ms"
    )
    if result.category is None:  # only the cap escalates without a classification
        return f"ESCALATED automatically - {result.escalation_reason}, {totals}"
    return (
        f"category={result.category} priority={result.priority}, "
        f"escalated={result.escalated}, {totals}"
    )


def classify(
    ticket: Ticket,
    client: Anthropic,
    approve: Callable[[str], bool],
    log_file_id: str | None = None,
) -> ClassifiedTicket:
    """Run the agent loop for one ticket and log its reasoning trace.

    The loop (reason, call a tool, observe, repeat) is capped at ``max_iterations``;
    hitting the cap counts as an automatic escalation. ``approve`` is the human
    gate for ``escalate_to_human``. ``log_file_id`` (an uploaded file) is attached to
    the prompt so the code execution sandbox can read it.
    """
    settings = get_settings()
    escalation = Escalation(approve)
    logger.info("Classifying ticket %s", ticket.id)

    runner = build_runner(client, ticket, escalation, log_file_id, settings)
    final, stats = run_loop(runner, ticket.id, settings)
    logger.debug("Ticket %s finished, stop_reason=%s", ticket.id, final.stop_reason)

    result = to_result(final, escalation, ticket, settings.max_iterations)
    log_final(ticket.id, summarize(result, stats))
    append_jsonl(settings.trace_file, final_record(result, stats))
    return result
