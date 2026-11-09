# ScoutBot — Week 11 Day 1 Starting Point

This is where today starts: **the finished Week 10 agent.** Over the last four weeks ScoutBot became one
capable, composed agent. It routes and grounds and cites (Week 9), remembers a customer, pauses for
approval and sends once (Week 8), calls a tool it didn't write over MCP and *is* a tool server (Week 10
Days 1–2), guards and audits its tool calls and delegates to a subagent (Day 3), and produces a validated
triage from a typed contract (Day 4). Week 10 Day 5 wired all of it into one `resolve_ticket`: **classify
with a contract, then resolve with tools.**

That is one agent doing everything, and it has a ceiling of a different kind than Week 10's. The single
prompt grows, the tools blur together, and a change to the refund path risks the order path. Today you do
what engineering always does when one thing does too much: **split it into specialists, and put an
orchestrator in front to route the work.**

You will build the **orchestrator-worker** topology as a LangGraph graph whose workers are **subgraphs**:

```
START -> look_up_customer -> dispatch -> (refund | order | research) -> finalize -> END
```

What you have:

- `src/scoutbot/graph.py` — the monolithic ticket graph (Weeks 8–9): one `StateGraph` that looks up the
  customer, triages, routes, retrieves, drafts, checks policy, and sends. Read `ticket_graph_builder` to
  see how nodes, `add_edge`, and `add_conditional_edges` fit together — today reuses exactly those
  primitives at a higher level.
- `src/scoutbot/policy.py` — the refund rules table (`decide_approval`). No model, no network — your
  **refund worker** reuses it directly.
- `src/scoutbot/knowledge.py` — Week 9's retrieval (`KnowledgeBase.search`, `format_passages`). Your
  **research worker** reuses it.
- `src/scoutbot/mcp_client.py`, `mock_orders.json` — the order-status tool from Week 10 Day 1. Your
  **order worker** reuses an order lookup.
- `src/scoutbot/stack.py` — Week 10 Day 5's `resolve_ticket`, the one-agent composition today splits apart.
- `tests/` — the full Week 10 suite, all passing. Today's tests reuse the same offline habits: pure routers
  tested with hand-made dicts, workers invoked directly with stubbed collaborators.

## Three things worth knowing before you start

**1. An orchestrator routes; a worker works.** The orchestrator's job is to decide *who* handles a ticket,
not to handle it. That decision is a router — a plain function from state to a node name — so it is
testable with a hand-made dict and no graph, exactly like Week 8 Day 2's routers.

**2. A worker is a subgraph, and subgraphs share state by key.** Each specialist is its own small
`StateGraph`, compiled and dropped into the parent as one node. It reads and writes the *same* state keys as
the parent, which is what lets one customer lookup at the top be visible to whichever specialist runs.

**3. Shared reducer channels are the one trap.** A compiled subgraph re-emits every channel it holds, so if
a worker shares the parent's `operator.add` channel (the run transcript), the parent adds it a second time
and the log double-counts. Keep the accumulator at the orchestrator level; give workers their own plain
data channels. (This is today's version of Week 8's "who owns which field" lesson.)

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — only the older reasoning demos need it
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

**No new dependency today.** Multi-agent orchestration is built from LangGraph primitives you already have
(`langgraph` has been in the stack since Week 8). The orchestrator you build today runs with **no API key**
at all — the dispatcher is a rule and the workers reuse deterministic pieces.

## Run

```bash
uv run python run_stack.py   # Week 10 Day 5: one agent, one ticket — classify, then resolve
uv run python run_typed.py   # Week 10 Day 4: the framework produces a validated triage
uv run python run_hooks.py   # Week 10 Day 3: a guard before a tool, an audit after it
uv run python run_mcp.py     # Week 10 Day 1: the model calls an order-status tool served over MCP
uv run python run_graph.py   # Week 8/9: the monolithic ticket graph, streamed
uv run pytest                # the Week 10 suite, passing, before you change anything
```
