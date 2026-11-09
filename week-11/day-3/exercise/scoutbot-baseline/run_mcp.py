"""Week 10 Day 1 in one script: ScoutBot answers using a tool it did not write.

The order-status tool does not live in the `scoutbot` package. It is published by a separate
program, `order_status_server.py`, and reached over the Model Context Protocol. This script
starts that server as a subprocess (stdio transport), hands the connection to the agent loop as
an `MCPToolProvider`, and runs two tickets:

    python run_mcp.py

The first ticket asks about a specific order, so the model should discover and call
`get_order_status` over the protocol and answer from what comes back. The second asks about an
order that does not exist, so the tool returns `found: false` and the model should say so plainly
rather than invent a status. Each step is printed so you can see the MCP tool call happen - the
action name is the server's tool, and the observation is what travelled back over the protocol.

The loop makes real Anthropic calls, so this needs `ANTHROPIC_API_KEY` in the environment (or a
.env file). The MCP server itself is fully local - no network, no key.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

from scoutbot.loop import run_agent_loop
from scoutbot.mcp_client import stdio_provider

load_dotenv()

HERE = Path(__file__).parent
SERVER = HERE / "order_status_server.py"

# (ticket_id, customer_id, question). The first names a real order (see mock_orders.json); the
# second names one that isn't there, so the tool answers found=false and the model must not guess.
TICKETS = [
    ("T-1001", "1001", "Where is my order ORD-1042? It's been a few days and I'm getting nervous."),
    ("T-1002", "1002", "Can you check the status of order ORD-9999 for me?"),
]


def _run_one(mcp, ticket_id: str, customer_id: str, question: str) -> None:
    print(f"=== {ticket_id}: {question} ===")
    result = run_agent_loop(question, customer_id, ticket_id=ticket_id, mcp=mcp)
    for i, step in enumerate(result.steps, start=1):
        if step.action:
            print(f"  step {i}: {step.action}({step.action_input}) -> {step.observation}")
        else:
            print(f"  step {i}: (final) {step.thought}")
    print(f"  answer: {result.final_answer}\n")


def main() -> None:
    # Launch the order server as a subprocess and talk to it over stdio - the same way a desktop
    # MCP host would. Running this file with the current interpreter keeps the venv consistent.
    mcp = stdio_provider(sys.executable, [str(SERVER)])
    print(f"Connected to MCP server: {[t['name'] for t in mcp.tool_schemas()]}\n")
    for ticket_id, customer_id, question in TICKETS:
        _run_one(mcp, ticket_id, customer_id, question)


if __name__ == "__main__":
    main()
