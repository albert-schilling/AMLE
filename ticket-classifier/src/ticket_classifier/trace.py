"""Printing of the agent loop's reasoning trace (Thought / Action / Observation)."""

from typing import Any


def print_step(step: int, message: Any, observation: Any) -> None:
    print(f"--- step {step} ---")
    for block in message.content:
        if block.type == "text" and block.text.strip():
            print(f"Thought: {block.text.strip()}")
        elif block.type == "tool_use":
            print(f"Action: {block.name}({block.input})")
    if observation is not None:
        for result in observation["content"]:
            print(f"Observation: {result['content']}")


def print_final(ticket_id: str, summary: str) -> None:
    print(f"=== {ticket_id}: {summary} ===\n")
