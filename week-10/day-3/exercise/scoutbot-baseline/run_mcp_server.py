"""Week 10 Day 2 in one script: ScoutBot's own capabilities, used by an outside client.

Yesterday ScoutBot was the client. Today it is the server: `scoutbot_mcp_server.py` publishes two of
ScoutBot's existing capabilities - policy search and customer lookup - over MCP. This script plays the
part of *another* program that wants to use them. It reuses yesterday's exact client
(`scoutbot.mcp_client.stdio_provider`), launches the server as a subprocess, discovers its tools, and
calls them - without importing any of ScoutBot's tool code:

    python run_mcp_server.py

The point is the direction of the arrow. Nothing here imports `scoutbot.knowledge` or `scoutbot.tools`;
it only speaks the protocol. So ScoutBot has become reusable infrastructure: any MCP client - a
different agent, a colleague's script, a desktop host - can now search the policy corpus and look up a
customer, exactly the way this script does.

No Anthropic key is needed: these are direct tool calls, not a reasoning loop. The first policy search
builds/opens `knowledge.db`, which downloads the embedding model once and is offline after that; the
customer lookup is a pure file read.
"""
import sys
from pathlib import Path

from scoutbot.mcp_client import stdio_provider

HERE = Path(__file__).parent
SERVER = HERE / "scoutbot_mcp_server.py"


def main() -> None:
    # Yesterday's client, pointed at today's server. Running with the current interpreter keeps the venv
    # consistent so the subprocess can import scoutbot.
    client = stdio_provider(sys.executable, [str(SERVER)])
    tools = client.tool_schemas()
    print(f"Discovered ScoutBot's published tools: {[t['name'] for t in tools]}\n")

    print("=== search_policy('how long until my refund arrives?') ===")
    passages = client.call("search_policy", {"query": "how long until my refund arrives?", "k": 2})
    for p in passages.get("result", passages) if isinstance(passages, dict) else passages:
        print(f"  [{p['source']}] ({p['score']:.2f}) {p['text'][:90]}...")
    print()

    print("=== look_up_customer('1001') ===")
    customer = client.call("look_up_customer", {"customer_id": "1001"})
    print(f"  {customer}\n")

    print("These are ScoutBot's own capabilities - now callable by anything that speaks MCP.")


if __name__ == "__main__":
    main()
