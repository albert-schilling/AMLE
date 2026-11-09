"""Week 10 Day 1: the MCP client, tested fully offline.

No subprocess and no network here. Each test builds a tiny `FastMCP` server in-process and hands
it to `in_memory_provider`, which wires it straight to a client with the SDK's in-memory transport
(`create_connected_server_and_client_session`). That exercises the exact discovery-and-call path
`stdio_provider` uses in the demo - list the tools, translate their schemas, forward a call - just
without the process boundary. It is the MCP analogue of patching `scoutbot.loop._client`.

The loop-level test at the bottom combines both fakes: a patched Anthropic client that asks for an
MCP tool by name, and an in-memory provider that serves it - so we can prove the loop dispatches an
MCP tool over the provider and feeds the result back, without any real model or any real server.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

from scoutbot.loop import run_agent_loop
from scoutbot.mcp_client import in_memory_provider


def _server() -> FastMCP:
    """A small MCP server with one well-typed tool and one that raises, for the error path."""
    server = FastMCP("test-orders")

    @server.tool()
    def get_order_status(order_id: str) -> dict:
        """Return the status of an order by id."""
        if order_id == "ORD-1":
            return {"found": True, "order_id": order_id, "status": "in_transit"}
        return {"found": False, "order_id": order_id}

    @server.tool()
    def always_breaks(x: str) -> str:
        """A tool that always raises, to exercise the error observation."""
        raise ValueError("boom")

    return server


def test_tool_schemas_are_translated_into_anthropic_shape():
    provider = in_memory_provider(_server())
    schemas = provider.tool_schemas()

    by_name = {s["name"]: s for s in schemas}
    assert set(by_name) == {"get_order_status", "always_breaks"}
    # The schema is the server's, in the Anthropic tool shape: name, description, input_schema.
    status = by_name["get_order_status"]
    assert set(status) == {"name", "description", "input_schema"}
    assert "order" in status["description"].lower()
    # And the input schema came from the tool's type hints - order_id: str, required.
    props = status["input_schema"]["properties"]
    assert props["order_id"]["type"] == "string"
    assert status["input_schema"]["required"] == ["order_id"]


def test_has_tool_reports_only_the_servers_tools():
    provider = in_memory_provider(_server())
    assert provider.has_tool("get_order_status") is True
    assert provider.has_tool("look_up_customer") is False  # a native tool, not this server's


def test_calling_a_tool_returns_its_structured_result():
    provider = in_memory_provider(_server())
    observation = provider.call("get_order_status", {"order_id": "ORD-1"})
    assert observation == {"found": True, "order_id": "ORD-1", "status": "in_transit"}


def test_a_not_found_result_is_data_not_an_error():
    provider = in_memory_provider(_server())
    observation = provider.call("get_order_status", {"order_id": "ORD-404"})
    # found=false is a normal answer the model should relay, not an error to recover from.
    assert observation == {"found": False, "order_id": "ORD-404"}


def test_a_raising_tool_comes_back_as_an_error_observation():
    provider = in_memory_provider(_server())
    observation = provider.call("always_breaks", {"x": "anything"})
    assert "error" in observation


def test_schemas_are_listed_once_and_cached():
    provider = in_memory_provider(_server())
    first = provider.tool_schemas()
    second = provider.tool_schemas()
    assert first is second  # cached: a server's tool list is fixed within a run


# --- loop integration: the model asks for an MCP tool, the provider serves it -----------------


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(name, input_, tool_use_id="toolu_mcp_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=tool_use_id)


def _response(*blocks):
    return SimpleNamespace(content=list(blocks))


@patch("scoutbot.loop._client")
def test_the_loop_dispatches_an_mcp_tool_over_the_provider(mock_client):
    mock_client.return_value.messages.create.side_effect = [
        _response(
            _text_block("Let me check the order status."),
            _tool_use_block("get_order_status", {"order_id": "ORD-1"}),
        ),
        _response(_text_block("Your order ORD-1 is in transit.")),
    ]

    provider = in_memory_provider(_server())
    result = run_agent_loop("Where is ORD-1?", customer_id="1001", mcp=provider)

    assert result.final_answer == "Your order ORD-1 is in transit."
    assert result.steps[0].action == "get_order_status"
    # The observation is what came back over the protocol, fed in as the loop's Observation.
    assert result.steps[0].observation == {
        "found": True,
        "order_id": "ORD-1",
        "status": "in_transit",
    }


@patch("scoutbot.loop._client")
def test_without_a_provider_an_mcp_tool_name_is_unknown(mock_client):
    # No provider passed: the MCP tool name falls through to the native dispatch, which does not
    # know it - proving the tools are only present when a provider is wired in.
    mock_client.return_value.messages.create.side_effect = [
        _response(
            _text_block("Trying a tool that isn't connected."),
            _tool_use_block("get_order_status", {"order_id": "ORD-1"}),
        ),
        _response(_text_block("done")),
    ]

    result = run_agent_loop("Where is ORD-1?", customer_id="1001")
    assert result.steps[0].observation == {"error": "Unknown tool: get_order_status"}
