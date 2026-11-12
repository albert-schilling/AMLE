"""The agent loop's trace (Thinking / Thought / Action / Observation) as log records.

Uses its own logger so the console can show it in a plain format while a log file
(``LOG_FILE``) gets timestamps. See ``logging_config.py``.
"""

import logging
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
