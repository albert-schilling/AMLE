"""A tiny MCP server, standing in for Anchorpoint's order-tracking system.

This is deliberately *not* part of the `scoutbot` package. It is a separate program that
publishes one tool - `get_order_status` - over the Model Context Protocol. ScoutBot reaches it
as a client (see `run_mcp.py` and `scoutbot.mcp_client`), the same way it would reach a tool
server written by another team, in another language, running in another process. That
separation is the entire point of Day 1: the agent uses a tool it did not write and cannot import.

Run it directly to serve over stdio (how the demo and real MCP hosts launch it):

    python order_status_server.py

Or inspect it interactively with the MCP Inspector:

    mcp dev order_status_server.py

With `FastMCP`, the type hints *are* the schema: `get_order_status(order_id: str) -> dict`
becomes a tool whose input is a required string `order_id`, with no JSON Schema written by hand.
"""
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ORDERS_PATH = Path(__file__).parent / "mock_orders.json"

mcp = FastMCP("anchorpoint-orders")


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """Look up the shipping status of a single order by its order_id (e.g. "ORD-1042").

    Returns the order's status, carrier, and estimated delivery date. If the order_id is not
    found, returns {"found": false, "order_id": ...} so the caller can tell the customer plainly
    rather than inventing a status.
    """
    orders = json.loads(ORDERS_PATH.read_text())
    record = orders.get(order_id)
    if record is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id, **record}


if __name__ == "__main__":
    mcp.run()
