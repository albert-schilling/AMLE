# ScoutBot — Week 10 Day 1 Starting Point

This is where today starts: **the finished Week 9 agent.** Over the last two weeks ScoutBot learned to
retrieve, ground and cite, loop and self-correct, route by effort, and remember a customer across
tickets. But every tool it uses, *we* wrote: a Python function plus a hand-written JSON schema in
`tools.py`, dispatched by name in the loop. That is a ceiling. The moment a ticket needs something
another team's system owns — a live order status, an invoice, a shipment — the bot is stuck, because it
can only use tools that live in our own package.

Today you lift that ceiling. ScoutBot becomes a client of the **Model Context Protocol (MCP)**: it
connects to a *separate* server, discovers the tools that server publishes, and calls one over the
protocol when the model asks — without ever importing the server's code.

What you have:

- `src/scoutbot/loop.py` — the ReAct tool-calling loop. Native tools (`look_up_customer`,
  `escalate_to_human`, `triage_ticket`) and Anthropic's server tools are assembled into `ALL_TOOLS` and
  dispatched in `_execute_client_tool`. **This is where today's one integration lands** — one optional
  argument, one list concatenation, one dispatch branch.
- `src/scoutbot/tools.py` — the native client tools, each a function plus a **hand-written** JSON schema.
  Contrast this today with how a `FastMCP` server derives its schema from type hints.
- `src/scoutbot/core.py`, `graph.py`, `knowledge.py`, `memory.py` — the rest of the Week 9 agent: triage,
  routing, the grounded/cited draft, the retrieval loop, per-customer memory. Untouched today.
- `tests/` — the full Week 9 suite, all passing. Today's tests patch the Anthropic client exactly as
  `tests/test_loop.py` already does, and add an in-memory MCP server so nothing spawns a subprocess.

## Three things worth knowing before you start

**1. A protocol splits the tool's provider from its consumer.** A *server* publishes tools — each a name,
a description, and a JSON schema. A *client* discovers and calls them, without importing the server. So
one client can reach many servers, written by anyone, in any language. ScoutBot becomes that client; the
order-status tool lives in a server it never imports.

**2. A discovered tool arrives in the same shape as a native one.** MCP describes a tool with a `name`, a
`description`, and an `inputSchema` that *is* JSON Schema — the same fields Anthropic's tool format wants.
Translating one into the other is almost a rename. So the model cannot tell an MCP tool from a local one;
**only the dispatch differs** — the server runs its own tool, we run ours.

**3. The tests stay offline, the framework-native way.** The MCP SDK ships an in-memory transport
(`create_connected_server_and_client_session`) that wires a `FastMCP` instance straight to a client with
no subprocess and no network. That is the MCP analogue of patching the Anthropic client. The runnable
demo uses stdio (a real subprocess); the tests never do.

## Setup

```bash
cp .env.example .env         # ANTHROPIC_API_KEY — the loop's reasoning is a real call
uv sync                      # creates .venv/ and installs the locked dependencies, pytest included
uv add "mcp[cli]>=1.29,<2"   # new today; the baseline omits it on purpose, so this is step 1
```

`fastembed` and `numpy` come in with `uv sync` (they arrived in Week 9). The one new dependency today
is `mcp[cli]` — the official Model Context Protocol SDK, which gives you both the `FastMCP` server and the
client. Keep the `<2` pin: the v2 line is a pre-release that renames `FastMCP`.

## Run

```bash
uv run python run_memory.py     # Week 9 Day 5: the same customer twice, the second recalls the first
uv run python run_router.py     # Week 9 Day 4: classify the ticket, then retrieve as hard as it deserves
uv run python run_agentic.py    # Week 9 Day 3: formulate a query, retrieve, critique, reword, then draft
uv run python run_rag.py        # Week 9 Day 2: retrieve once, draft a grounded, cited reply
uv run python run_approval.py   # Week 8 Thursday: policy, pause, send once
uv run python main.py           # Week 7's loop, unchanged
uv run pytest                   # the Week 9 suite, passing, before you change anything
```
