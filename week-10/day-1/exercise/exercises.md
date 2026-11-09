# W10D1 Exercise — Let ScoutBot Use a Tool It Didn't Write

## Scenario

A customer asks where their order is *right now*. ScoutBot has no tool for that, and it never will if we
keep the current habit — because the order-tracking system belongs to another team, in another codebase,
maybe another language. Every tool ScoutBot has today is one *we* wrote: a Python function plus a
hand-written JSON schema in `tools.py`, dispatched by name in the loop. That is a ceiling.

Today you lift it. ScoutBot becomes a client of the **Model Context Protocol (MCP)**. A *server* publishes
tools; a *client* discovers and calls them, without importing the server's code. You will write a tiny
example server that publishes an order-status tool, a client that connects and forwards calls, and one
dispatch branch in the loop so the model can call a tool that lives in a completely separate process.

The trick is how *little* the loop changes. A tool discovered over MCP arrives in the **same shape** as a
native one — a name, a description, a JSON input schema — so the model can't tell them apart. The only
difference is who runs the call: we run our native tools; the server runs its own.

## Starting point

`scoutbot-baseline/` is **the finished Week 9 agent**: it routes, grounds, cites, loops, remembers a
customer, pauses for approval, and sends once. Everyone extends this same baseline, in place. Three things
to know:

- **The type hints are the schema.** A `FastMCP` tool is a plain typed function — `get_order_status(
  order_id: str) -> dict` — and the server derives its JSON schema from the hints. You do **not**
  hand-write an `input_schema` dict the way `tools.py` does.
- **A discovered tool plugs into the loop you already have.** MCP tools join `ALL_TOOLS`, the model calls
  one like any other, and the result comes back as an Observation. You do **not** build a parallel loop for
  MCP.
- **Tests stay offline with the in-memory transport.** `create_connected_server_and_client_session` wires
  a `FastMCP` instance straight to a client — no subprocess, no network. The `run_mcp.py` demo uses stdio
  (a real subprocess); the tests never do.

## Your task

Working in pairs, on a new branch. First `uv add "mcp[cli]>=1.29,<2"` (the one new dependency; the `<2` pin matters).

### Part 1 — An example server and a client (`order_status_server.py`, `mcp_client.py`)

1. **Write a `FastMCP` server with one typed tool.** New file `order_status_server.py` at the project
   root (not inside the `scoutbot` package — it is a *separate* program). Create a `FastMCP("...")`,
   decorate one function `@mcp.tool()`, e.g. `get_order_status(order_id: str) -> dict`, backed by a small
   `mock_orders.json`. Return a not-found order as data (`{"found": False, "order_id": ...}`), not an
   exception. End with `if __name__ == "__main__": mcp.run()` so it can serve over stdio.
2. **Build an `MCPToolProvider` (`src/scoutbot/mcp_client.py`).** It wraps an MCP client session and
   exposes three things the loop needs: `tool_schemas()` (the server's tools, translated into the
   Anthropic tool shape), `has_tool(name)`, and `call(name, args)` (forward the call, return an
   Observation dict).
3. **Translate the schema, don't convert it.** MCP describes a tool with `name`, `description`, and
   `inputSchema` (which *is* JSON Schema). Map those to Anthropic's `name`, `description`, `input_schema`.
   It is nearly a rename — that is the point of a protocol.
4. **Bridge async to sync at the boundary.** The MCP client is async; the loop is sync. Run each operation
   to completion with `asyncio.run` inside the provider (open a session, list or call, close). Do not make
   the loop async. Note aloud that a production client would pool the session; per-call connect is fine
   here.
5. **Turn a result into an Observation.** Most servers serialise a tool's return as JSON text, so parse
   that back into a dict. Surface a not-found result as data, and a *raised* tool as `{"error": ...}` so
   the model reacts to it like any failed local tool.
6. **Two ways to connect, one provider.** Provide `stdio_provider(command, args)` (launches the server as
   a subprocess — used by the demo) and `in_memory_provider(server)` (wires a `FastMCP` straight to a
   client with `create_connected_server_and_client_session` — used by the tests).

### Part 2 — Into the loop, a demo, and offline tests (`loop.py`, `run_mcp.py`, `tests/`)

7. **Add the provider's tools to what the model sees.** Give `run_agent_loop` an optional
   `mcp: MCPToolProvider | None = None`. When present, the tools passed to the API are
   `[*ALL_TOOLS, *mcp.tool_schemas()]`. When `None`, the call is byte-for-byte Week 9's.
8. **Dispatch MCP tools to the provider.** In `_execute_client_tool`, check the provider first: if
   `mcp is not None and mcp.has_tool(name)`, return `mcp.call(name, args)`; otherwise fall through to the
   native tools exactly as before. One branch — that is the whole integration.
9. **Nudge the model to use connected tools.** Add one sentence to the system prompt: extra tools may be
   available from connected services (for example, the status of a specific order), and it should call
   them rather than guessing.
10. **See it work (`run_mcp.py`).** Build a `stdio_provider` pointing at `order_status_server.py`, then run
    the loop on two tickets: one asking about a real order (the model should call `get_order_status`) and
    one about an order that doesn't exist (the tool returns `found: false`, and the model should say so
    plainly). Print each step so the MCP tool call is visible. This makes real Anthropic calls, so it needs
    a key.
11. **Test the client offline (`tests/test_mcp_client.py`).** Build a tiny `FastMCP` server *in the test*
    and hand it to `in_memory_provider`. Assert: the schema is translated into the Anthropic shape; a call
    returns the tool's structured result; a not-found result is data; a raising tool comes back as
    `{"error": ...}`. **No subprocess, no network.**
12. **Test the loop integration offline.** Reuse the existing `scoutbot.loop._client` patch to make the
    model *ask* for the MCP tool, pass an `in_memory_provider`, and assert the loop dispatched the call to
    the provider and fed the result back. Add the negative case: without a provider, that tool name is an
    Unknown tool.
13. **Same habit as every day**: commit on your branch, open a PR.

> **One gotcha worth naming.** The MCP client is async and the loop is sync. If you try to `await` inside
> the loop you will fight the event loop; instead run each provider operation with `asyncio.run`. And if a
> tool returns a plain `dict`, its value may come back only as JSON *text* (not `structuredContent`), so
> parse the text — don't assume `structuredContent` is always present.

## Expected outcome (minimum requirements)

- [ ] **A `FastMCP` server** publishes one typed tool; the schema comes from type hints, not a hand-written
  dict
- [ ] **`MCPToolProvider`** connects, lists tools, translates schemas, and forwards calls
- [ ] **MCP schemas become Anthropic tools** — `name`, `description`, `input_schema`
- [ ] **The loop dispatches MCP tool names to the provider**, native names to the native table
- [ ] **A result comes back as an Observation** — not-found is data, a raise is `{"error": ...}`
- [ ] **`stdio_provider` and `in_memory_provider`** both build the same provider
- [ ] **`run_mcp.py`** shows the model calling a tool that lives in a separate server
- [ ] **Offline tests**: the client (translate, call, not-found, error) and the loop integration, all
  in-memory — no subprocess, no network
- [ ] **The Week 9 suite still passes** — the integration is additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Publish a second tool.** Add another `@mcp.tool()` to the server (say, `list_recent_orders(customer_id:
  str)`), and confirm it shows up in `tool_schemas()` and is callable — with no change to the loop.
- **Handle a slow or failing server.** What happens if the tool raises, or the subprocess dies? Make the
  provider surface a clean `{"error": ...}` Observation rather than crashing the loop, and test it.
- **Inspect the server with the MCP Inspector.** Run `mcp dev order_status_server.py` and click through the
  published tools. What does the client see that your translation throws away?
- **Pool the session.** Right now the provider connects per call. Sketch (or build) a version that opens the
  session once and reuses it. Where does the sync/async boundary get harder, and what do you gain?
- **Two clients, one server.** Point a second, throwaway client at your running server. What does it mean
  that the tool is now usable by anything that speaks the protocol, not just ScoutBot?

## If you're running out of time

Protect steps 1–2 (the server and the provider), step 7 and step 8 (the loop sees the tools and dispatches
them), and step 11 (the client tested in-memory). That round-trip — a tool published by a separate server,
discovered and called through the loop, proven by a test that never spawns a process — is what the day is
assessed on. Trim `run_mcp.py`'s second ticket (step 10) and the loop-integration test (step 12) first, and
keep the schema translation honest (step 3). Do **not** skip the in-memory transport in tests (step 6): a
suite that spawns a subprocess works but is slow and flaky, and offline-testability is half the point of the
day. Flag whatever you skipped rather than quietly leaving it out. (Coaches: see the coaches' page
"Contingency plans" for exactly what to prioritise.)
