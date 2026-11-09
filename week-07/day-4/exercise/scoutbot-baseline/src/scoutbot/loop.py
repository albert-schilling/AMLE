"""The Day 2 agent loop: reason, act, observe, repeat - implemented as ReAct on top of
Anthropic's tool calling, with a hard iteration cap and one human-in-the-loop gate.

Deliberately simple, matching Day 1's conventions:
- No injected client abstraction - `_client()` talks to the real Anthropic SDK directly; tests
  patch `scoutbot.loop._client` to run offline (see tests/test_loop.py).
- One tool call handled per turn (the model can ask for more than one; we only execute the
  first and let the next turn pick up from there) - keeps the trace simple to read and log.
- No retry-on-malformed-output logic here (unlike yesterday's `triage()`) - a bad tool call in
  the loop just becomes an Observation the model sees and can react to, which is closer to how
  ReAct actually recovers from mistakes.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from anthropic import Anthropic

from .core import TRIAGE_TOOL
from .schema import TicketTriage
from .tools import ESCALATE_TOOL, LOOK_UP_CUSTOMER_TOOL, escalate_to_human, look_up_customer

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
MAX_STEPS = 6

ALL_TOOLS = [TRIAGE_TOOL, LOOK_UP_CUSTOMER_TOOL, ESCALATE_TOOL]

SYSTEM_PROMPT = (
    "You are ScoutBot, a support-ticket resolution assistant for Anchorpoint. For each ticket: "
    "briefly say what you're about to do and why (one sentence), then either call exactly one "
    "tool, or - once you have everything you need - give your final answer as plain text with "
    "no tool call. Use look_up_customer before deciding on anything account-specific. Use "
    "escalate_to_human for anything you're not confident resolving yourself; it requires human "
    "approval, so calling it is safe even if you're unsure."
)


@dataclass
class LoopStep:
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    observation: Optional[dict] = None


@dataclass
class AgentResult:
    final_answer: str
    steps: list = field(default_factory=list)
    escalated: bool = False


def _client() -> Anthropic:
    return Anthropic()


def _execute_tool(name: str, args: dict, approve_fn: Optional[Callable[[str], bool]]) -> dict:
    if name == "look_up_customer":
        return look_up_customer(args["customer_id"])
    if name == "escalate_to_human":
        return escalate_to_human(args["reason"], approve_fn=approve_fn)
    if name == "triage_ticket":
        return TicketTriage.model_validate(args).model_dump()
    return {"error": f"Unknown tool: {name}"}


def run_agent_loop(
    ticket_text: str,
    customer_id: str,
    max_steps: int = MAX_STEPS,
    approve_fn: Optional[Callable[[str], bool]] = None,
) -> AgentResult:
    """Run ScoutBot's ReAct loop on one ticket until it gives a final answer or hits the
    iteration cap (in which case it's treated as an automatic escalation)."""
    messages = [
        {"role": "user", "content": f"Ticket (customer_id={customer_id}): {ticket_text}"}
    ]
    steps = []

    for _ in range(max_steps):
        response = _client().messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=ALL_TOOLS,
        )
        thought = "".join(block.text for block in response.content if block.type == "text").strip()
        tool_uses = [block for block in response.content if block.type == "tool_use"]

        if not tool_uses:
            steps.append(LoopStep(thought=thought))
            return AgentResult(final_answer=thought, steps=steps)

        tool_use = tool_uses[0]
        observation = _execute_tool(tool_use.name, tool_use.input, approve_fn)
        steps.append(
            LoopStep(
                thought=thought,
                action=tool_use.name,
                action_input=tool_use.input,
                observation=observation,
            )
        )
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(observation),
                    }
                ],
            }
        )

    steps.append(LoopStep(thought=f"Hit the {max_steps}-step cap without a final answer."))
    return AgentResult(
        final_answer="Couldn't resolve this automatically within the step limit - escalating to a human.",
        steps=steps,
        escalated=True,
    )
