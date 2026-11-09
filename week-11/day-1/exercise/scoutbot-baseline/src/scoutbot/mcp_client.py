"""ScoutBot as an MCP *client*: how Week 10 Day 1 lets the agent call a tool it did not
write, served over a protocol instead of hand-wired as a Python function.

Every tool ScoutBot has used so far (`look_up_customer`, `escalate_to_human`, the triage
tool) lives *inside* this codebase: a Python function plus a hand-written JSON schema in
`tools.py`, dispatched by name in `loop._execute_client_tool`. That works, but it means the
agent can only ever use tools we ship in our own package. The **Model Context Protocol (MCP)**
breaks that coupling: a *server* publishes tools (each with a name, a description, and a JSON
schema), and any *client* that speaks MCP can discover and call them - without importing the
server's code, or even being written in the same language.

Today ScoutBot becomes that client. `MCPToolProvider` connects to a server, asks it what tools
it has (`list_tools`), and hands those tools to the agent loop in the *same* Anthropic tool
shape the native tools already use - so from the model's point of view an MCP tool and a local
tool are indistinguishable. When the model calls one, the provider forwards the call over the
protocol (`call_tool`) and returns the result as the loop's Observation.

**Why a sync facade over an async protocol.** The MCP client API is async, but ScoutBot's loop
(and its graph nodes) are synchronous, exactly as they have been since Week 7. Rather than turn
the whole agent async, this module keeps one thin bridge: each public method runs a short async
body to completion with `asyncio.run`. That reconnects for each operation, which is fine at this
scale and honest to teach - a production client would open the session once and pool it, but the
protocol semantics are identical either way, and per-call connect keeps the code readable and
the tests trivial to run.

**Two ways to connect, one provider.** `stdio_provider(...)` launches a server as a subprocess
and talks to it over stdin/stdout - what the `run_mcp.py` demo uses, and what desktop MCP hosts
do. `in_memory_provider(server)` wires a `FastMCP` instance straight to a client with no process
and no network - the MCP analogue of "mock the SDK client", and what the offline tests use. Both
return the same `MCPToolProvider`, so the loop never knows or cares which transport is underneath.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, Optional, TypeVar

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

T = TypeVar("T")

# A `Connect` opens an MCP session for the duration of an `async with` and yields it. Both
# transports below are packaged as one of these, so `MCPToolProvider` is transport-agnostic.
Connect = Callable[[], "AbstractAsyncSession"]


def _to_anthropic_tool(mcp_tool: Any) -> dict:
    """Translate one MCP tool definition into the tool dict the Anthropic API expects.

    The shapes line up almost exactly: MCP already describes a tool with a `name`, a
    `description`, and an `inputSchema` that *is* JSON Schema - the same JSON Schema the
    Anthropic `input_schema` field wants. So this is a rename, not a conversion, which is
    the whole point of a protocol: the tool's contract travels with it, ready to use.
    """
    return {
        "name": mcp_tool.name,
        "description": mcp_tool.description or "",
        "input_schema": mcp_tool.inputSchema,
    }


def _result_to_observation(result: Any) -> dict:
    """Turn an MCP `call_tool` result into the plain dict the loop uses as an Observation.

    Every tool result carries its return value serialized as JSON in a text block; a tool that
    declares a non-object return type *also* mirrors it under `structuredContent` (wrapped as
    `{"result": ...}`). So the robust reading is: an object return parses straight back into a
    dict from the text, and a scalar/list return is surfaced under `structuredContent` or a
    `result` key. An error is surfaced as `{"error": ...}` so the model sees it as an Observation
    to react to, exactly like a failed local tool call.
    """
    if getattr(result, "isError", False):
        return {"error": _join_text(result) or "tool call failed"}
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    text = _join_text(result)
    if not text:
        return {"text": ""}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _join_text(result: Any) -> str:
    blocks = getattr(result, "content", None) or []
    return "".join(getattr(b, "text", "") for b in blocks).strip()


class MCPToolProvider:
    """Presents an MCP server's tools to the agent loop as if they were native tools.

    Holds no open connection between calls: every method runs a short async body with
    `asyncio.run`, connecting through the `connect` factory it was given and closing again.
    The first `tool_schemas()` result is cached, since a server's tool list does not change
    within a run and the loop asks for it on every turn.
    """

    def __init__(self, connect: Connect):
        self._connect = connect
        self._schemas: Optional[list[dict]] = None
        self._names: Optional[set[str]] = None

    def _run(self, coro: Awaitable[T]) -> T:
        return asyncio.run(coro)

    async def _list_tools(self) -> list:
        async with self._connect() as session:
            await session.initialize()
            return (await session.list_tools()).tools

    async def _call_tool(self, name: str, args: dict) -> dict:
        async with self._connect() as session:
            await session.initialize()
            return _result_to_observation(await session.call_tool(name, args))

    def tool_schemas(self) -> list[dict]:
        """The server's tools, in Anthropic tool shape, ready to append to `ALL_TOOLS`."""
        if self._schemas is None:
            tools = self._run(self._list_tools())
            self._schemas = [_to_anthropic_tool(t) for t in tools]
            self._names = {t["name"] for t in self._schemas}
        return self._schemas

    def has_tool(self, name: str) -> bool:
        """Whether `name` is served over MCP - the loop uses this to decide who dispatches it."""
        if self._names is None:
            self.tool_schemas()
        return name in (self._names or set())

    def call(self, name: str, args: dict) -> dict:
        """Forward one tool call over the protocol and return its result as an Observation."""
        return self._run(self._call_tool(name, args))


# `AbstractAsyncSession` is just "whatever `async with connect()` yields" - a `ClientSession`.
# Named only so the `Connect` type reads clearly; there is no separate class to implement.
AbstractAsyncSession = AsyncIterator[ClientSession]


def stdio_provider(command: str, args: list[str], env: Optional[dict] = None) -> MCPToolProvider:
    """A provider that launches an MCP server as a subprocess and talks to it over stdio.

    This is how real MCP hosts (Claude Desktop, IDEs) run local servers, and what `run_mcp.py`
    uses to reach `order_status_server.py`. The subprocess is started and stopped around each
    operation - see the module docstring on why per-call connect is fine here.
    """
    params = StdioServerParameters(command=command, args=args, env=env)

    @asynccontextmanager
    async def connect() -> AsyncIterator[ClientSession]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                yield session

    return MCPToolProvider(connect)


def in_memory_provider(server: Any) -> MCPToolProvider:
    """A provider wired straight to a `FastMCP` instance, with no subprocess and no network.

    The MCP analogue of patching the Anthropic client: tests build a tiny server, hand it here,
    and exercise the exact discovery-and-call path the stdio transport uses - just without the
    process boundary. Keeps Week 10's tests as offline and fast as every week before it.
    """

    def connect():
        return create_connected_server_and_client_session(server)

    return MCPToolProvider(connect)
