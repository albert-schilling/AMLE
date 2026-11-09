# ScoutBot (Week 8 Day 2 starting point)

This is Week 8 Day 1's reference solution: Week 7's ReAct loop, untouched, plus yesterday's
two-node LangGraph graph with an explicit state schema. Everyone starts today from this same
known-good baseline, regardless of how far you got yesterday. Nothing in here changes shape today,
you're extending it.

- `src/scoutbot/graph.py` — yesterday's graph. `TicketState` declares what one run accumulates,
  `look_up_customer_node` and `triage_ticket_node` each return only the fields they changed, and
  `build_ticket_graph()` wires them `START → look_up_customer → triage_ticket → END`. Today you add
  a branch after triage, and a checkpointer to `compile()`.
- `run_graph.py` — yesterday's demo. Streams updates and values together, so each node's own return
  value prints next to the merged state. Run it once before you start, to see where today begins.
- `src/scoutbot/core.py` / `schema.py` / `tools.py` / `server_tools.py` / `telemetry.py` — Week 7's
  triage logic, tools and step logger. Unchanged.
- `src/scoutbot/loop.py` — Week 7's bounded ReAct loop. Still not today's subject, and still should
  keep working when you're done. Worth one look, though: find where it escalates a ticket. It
  happens because the *model* chose to call `escalate_to_human`, which is exactly the kind of
  decision you're about to make explicit.
- `mock_customers.json` / `sample_tickets.json` / `sample_app.log` — the same fake data as Week 7.

**`langgraph` is already installed here** (it arrived yesterday). **The SQLite checkpointer is
not**, and adding it is one of today's steps, on purpose, so the dependency lands in your own
`pyproject.toml`.

**Your actual task is in [`../exercises.md`](../exercises.md)** — this folder is just the starting
point, not the instructions.

## Setup

```bash
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

## Run / test (as-is, before you change anything)

```bash
uv run python run_graph.py   # yesterday's graph, printing state after each node
uv run python main.py        # Week 7's loop on all 5 sample tickets
uv run pytest                # 37 tests should all pass, untouched
```
