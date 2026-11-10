"""The agent loop's reasoning trace (Thought / Action / Observation), as log records.

Uses its own logger so the console can show it in a plain format while a log file
(``LOG_FILE``) gets timestamps. See ``logging_config.py``.
"""

import logging
from typing import Any

TRACE_LOGGER_NAME = "ticket_classifier.trace"
trace_logger = logging.getLogger(TRACE_LOGGER_NAME)


def log_step(ticket_id: str, step: int, message: Any, observation: Any) -> None:
    prefix = f"[{ticket_id}] step {step}"
    for block in message.content:
        if block.type == "text" and block.text.strip():
            trace_logger.info("%s Thought: %s", prefix, block.text.strip())
        elif block.type == "tool_use":
            trace_logger.info("%s Action: %s(%s)", prefix, block.name, block.input)
    if observation is not None:
        for result in observation["content"]:
            trace_logger.info("%s Observation: %s", prefix, result["content"])


def log_final(ticket_id: str, summary: str) -> None:
    trace_logger.info("[%s] Final: %s", ticket_id, summary)
