# ScoutBot — Week 10 Day 2 Starting Point

This is where today starts: **your finished Week 10 Day 1 agent — the MCP client.** Yesterday ScoutBot
became a *client* of the Model Context Protocol: it connects to a separate server, discovers the tools
that server publishes, translates each into the Anthropic tool shape, and calls one over the protocol
when the model asks — without importing the server's code. The `order_status_server.py` example proved
it: the model called a tool that lived in a file `scoutbot` never imports.

Today you turn the protocol around. ScoutBot stops being only a *consumer* of tools and becomes a
**server** — a *provider*. You take two capabilities it already has (searching the support policy, and
looking up a customer) and publish them as MCP tools, so any client that speaks the protocol can use
them. The support bot becomes reusable infrastructure. The proof is satisfying: you point *yesterday's
client* at *today's server* and watch it call ScoutBot's own tools.

What you have:

- `src/scoutbot/mcp_client.py` — **yesterday's work, and today's proof.** The `MCPToolProvider` (a sync
  facade over the async MCP client), plus `stdio_provider` and `in_memory_provider`. You will point these
  at the server you write today; you should not need to change them.
- `order_status_server.py` — **the shape to copy.** A standalone `FastMCP` server publishing one typed
  tool (`get_order_status`), its schema derived from type hints. Today's server is the same shape, but its
  tools are ScoutBot's real capabilities.
- `src/scoutbot/tools.py` — `look_up_customer` lives here, a plain function you will *wrap and publish*
  (not reimplement). `src/scoutbot/knowledge.py` — the `KnowledgeBase` with a `search()` method your
  `search_policy` tool will call.
- `src/scoutbot/loop.py`, `core.py`, `graph.py`, `memory.py` — the rest of the agent, untouched today.
- `tests/` — the full suite, all passing, including yesterday's `tests/test_mcp_client.py`. Today's tests
  add one file that stands up your server on the in-memory transport with an injected stub knowledge base
  — no subprocess, no model download.

## Three things worth knowing before you start

**1. Same protocol, the other side.** Day 1 was one client reaching many servers; today is one server
reached by many clients. A server publishes tools — a name, a description, a JSON schema — and any client
that speaks MCP can list and call them, without importing your code. Publishing once means any agent, any
script, any desktop host can reuse what ScoutBot knows.

**2. The type hints are the schema.** A `FastMCP` tool is a plain typed function — `search_policy(query:
str, k: int = 3) -> list[dict]` — and the server derives its JSON schema from the annotations. There is
**no hand-written `input_schema`**, in deliberate contrast to `tools.py`. The signature you already write
is the contract.

**3. Inject what needs the network, so the tests stay offline.** `search_policy` needs a `KnowledgeBase`,
which needs an embedding model. Make it an argument — `build_server(kb=...)` — so your tests can pass a
tiny stub that returns a fixed list of hits (no model, no SQLite, no network) and reach the server over
the in-memory transport. This is the same "mock the collaborator" discipline every prior week used.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — only run_mcp.py's reasoning loop needs it
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

No new dependency today: `mcp[cli]` arrived on Day 1 and gives you both the client and the `FastMCP`
server. `uv sync` brings it in (pinned `<2` in `pyproject.toml`).

## Run

```bash
uv run python run_mcp.py                # Week 10 Day 1: the model calls an order-status tool served over MCP
uv run python run_memory.py             # Week 9 Day 5: the same customer twice, the second recalls the first
uv run python run_router.py             # Week 9 Day 4: classify the ticket, then retrieve as hard as it deserves
uv run python run_rag.py                # Week 9 Day 2: retrieve once, draft a grounded, cited reply
uv run python main.py                   # Week 7's loop, unchanged
uv run pytest                           # the full suite, passing, before you change anything

# the Day 1 example server can still be run or inspected on its own:
uv run python order_status_server.py    # serve over stdio
uv run mcp dev order_status_server.py   # open the MCP Inspector
```
