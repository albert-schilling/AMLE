"""The agent loop's trace (Thinking / Thought / Action / Observation) as log records.

Uses its own logger so the console can show it in a plain format while a log file
(``LOG_FILE``) gets timestamps. See ``logging_config.py``.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TRACE_LOGGER_NAME = "ticket_classifier.trace"
trace_logger = logging.getLogger(TRACE_LOGGER_NAME)


def log_actions(ticket_id: str, step: int, message: Any) -> None:
    """Log what the model said and wants to do. Call this *before* running the tools.

    Thinking blocks (extended thinking, ``THINKING_BUDGET``) are logged as Thinking.
    Text next to tool calls is a Thought; text in a message without tool calls is
    the final Answer.
    """
    prefix = f"[{ticket_id}] step {step}"
    has_tool_calls = any(block.type == "tool_use" for block in message.content)
    label = "Thought" if has_tool_calls else "Answer"
    for block in message.content:
        if block.type == "thinking" and block.thinking.strip():
            trace_logger.info("%s Thinking: %s", prefix, block.thinking.strip())
        elif block.type == "text" and block.text.strip():
            trace_logger.info("%s %s: %s", prefix, label, block.text.strip())
        elif block.type == "tool_use":
            trace_logger.info("%s Action: %s(%s)", prefix, block.name, block.input)
        elif block.type == "server_tool_use":  # run by Anthropic, already finished
            trace_logger.info("%s Action: %s(%s)", prefix, block.name, block.input)
        elif block.type == "web_fetch_tool_result":
            trace_logger.info("%s Observation: %s", prefix, describe_fetch(block))
        elif block.type in CODE_RESULT_TYPES:
            trace_logger.info("%s Observation: %s", prefix, describe_code(block))


CODE_RESULT_TYPES = (
    "bash_code_execution_tool_result",
    "text_editor_code_execution_tool_result",
)


def describe_code(block: Any) -> str:
    """Summary of a code execution result: stdout/stderr, or the error code."""
    result = block.content
    if result.type.endswith("_error"):
        return f"code execution failed: {result.error_code}"
    if result.type == "bash_code_execution_result":
        output = (result.stdout or result.stderr).strip()
        return f"code execution exit {result.return_code}: {output}"
    return f"code execution ok: {result.type}"


def describe_fetch(block: Any) -> str:
    """Short summary of a ``web_fetch`` result block (the page itself is not logged)."""
    result = block.content
    if result.type == "web_fetch_tool_result_error":
        return f"web_fetch failed: {result.error_code}"
    return f"web_fetch ok: {result.url}"


def log_observations(ticket_id: str, step: int, observation: Any) -> None:
    if observation is None:
        return
    prefix = f"[{ticket_id}] step {step}"
    for result in observation["content"]:
        trace_logger.info("%s Observation: %s", prefix, result["content"])


def log_final(ticket_id: str, summary: str) -> None:
    trace_logger.info("[%s] Final: %s", ticket_id, summary)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one record as a single JSON line (JSON Lines)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, default=str) + "\n")


def step_observation(message: Any, observation: Any) -> str | None:
    """What the step observed: client tool results plus finished server tool results."""
    parts = []
    for block in message.content:
        if block.type == "web_fetch_tool_result":
            parts.append(describe_fetch(block))
        elif block.type in CODE_RESULT_TYPES:
            parts.append(describe_code(block))
    if observation is not None:
        parts += [str(result["content"]) for result in observation["content"]]
    return "\n".join(parts) or None


def step_errored(message: Any, observation: Any) -> bool:
    """True if a tool raised (client) or returned an error result (server)."""
    server = any(
        block.content.type.endswith("_error")
        for block in message.content
        if block.type == "web_fetch_tool_result" or block.type in CODE_RESULT_TYPES
    )
    client = observation is not None and any(
        result.get("is_error") for result in observation["content"]
    )
    return server or client


def uses_container(message: Any) -> bool:
    """True if the step ran the code execution sandbox (billed by container time)."""
    return any(
        block.type == "server_tool_use" and "code_execution" in block.name
        for block in message.content
    )


def step_record(
    ticket_id: str,
    step: int,
    model: str,
    message: Any,
    observation: Any,
    duration_ms: int,
) -> dict[str, Any]:
    """One loop step as a dict: thought, action, action_input, observation, timing."""
    calls = [
        {"name": b.name, "input": b.input}
        for b in message.content
        if b.type in ("tool_use", "server_tool_use")
    ]
    thought = "\n".join(b.text.strip() for b in message.content if b.type == "text")
    return {
        "type": "step",
        "timestamp": datetime.now(UTC).isoformat(),
        "ticket_id": ticket_id,
        "step": step,
        "model": model,
        "thought": thought or None,
        "tool_calls": calls,  # a step can hold several calls
        "observation": step_observation(message, observation),
        "duration_ms": duration_ms,
        # the API reports no container time: the whole step time is an upper bound
        "container_ms_estimate": duration_ms if uses_container(message) else 0,
        "errored": step_errored(message, observation),
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }


def final_record(
    ticket_id: str,
    escalated: bool,
    category: str | None,
    steps: int,
    input_tokens: int,
    output_tokens: int,
    container_ms_estimate: int,
) -> dict[str, Any]:
    """The last line of a ticket: how it ended."""
    return {
        "type": "final",
        "timestamp": datetime.now(UTC).isoformat(),
        "ticket_id": ticket_id,
        "steps": steps,
        "escalated": escalated,
        "category": category,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "container_ms_estimate": container_ms_estimate,
    }
