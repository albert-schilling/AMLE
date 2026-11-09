# ScoutBot — Week 10 Day 5 Starting Point

This is where the week's finale starts: **your finished Week 10 Day 4 agent — a type-safe, contract-driven
triage agent.** By now ScoutBot is a pile of good, separately-built parts. It speaks MCP from both sides (a
client that calls tools it did not write, a server that publishes its own), it guards its tool calls with
pre- and post-hooks, it issues an idempotent refund, it can delegate a scoped policy question to a research
subagent, and it produces its `TicketTriage` through a Pydantic AI agent whose `output_type` the framework
enforces. Every one of those pieces is tested offline — and **none of them has ever run together.**

Today you wire them into one end-to-end run. You add **`stack.py`**: `assemble_stack` composes the week's
collaborators into one `Stack`, and `resolve_ticket` runs the integration pattern — **classify with a
contract, then resolve with tools.** You write `run_stack.py` to watch one ticket flow through the whole
thing, and `tests/test_stack.py` to prove the composition **offline**. Nothing new is invented; the day is
the assembly.

The theme: a production agent is a **composition of small, separately-tested patterns**, not one monolith.
The other half of the day is a **decision guide** — matching a problem to the pattern that solves it — which
is the piece you carry into Week 11 and the capstone.

What you have:

- `src/scoutbot/loop.py` — **the integration point.** `run_agent_loop` was additive from the start, so it
  already accepts `mcp`, `hooks`, `ledger`, `subagent`, and `log_path`. Read its signature first: wiring the
  stack is *passing arguments it already takes*, not surgery.
- `src/scoutbot/typed_agent.py` — **the classify half.** `typed_agent.triage(text, model=None)` returns a
  validated `TicketTriage`; `resolve_ticket` runs it *first*.
- `src/scoutbot/hooks.py` — `refund_guard` (a pre-hook) and `audit_hook` (a post-hook), plus `Hooks` and
  `run_hooked`.
- `src/scoutbot/tools.py`, `notify.py` — `issue_refund` and the idempotent `Ledger`.
- `src/scoutbot/subagent.py` — `ResearchSubagent`; `src/scoutbot/mcp_client.py` — `MCPToolProvider` and
  `stdio_provider`.
- `tests/` — the full suite, all passing (`217`, with a couple of embed-gated skips). Today's tests add one
  file, `tests/test_stack.py`, that drives the whole composed path with fake models and stubs.

## Three things worth knowing before you start

**1. Nothing new is invented — you are wiring, not building.** Every capability today's stack uses already
exists. `assemble_stack` composes them and `resolve_ticket` runs them in order. If you find yourself writing
a new tool or a new agent, you have misread the task: today is composition.

**2. The pattern is classify, then resolve.** `resolve_ticket` triages with the typed agent (a validated
`TicketTriage`), then hands the ticket to the fully-wired loop, and returns a `StackResult` bundling the
triage, the loop's result, and the audit trail. Two halves of a real ticket handler, run in order.

**3. Prove the composition offline.** The seams that made each piece testable make the *whole thing*
testable: the triage model is an argument (pass a `TestModel`), and the loop's `_client` is patchable (script
the turns). Add `StubKB`, a `FakeMCP`, and an in-memory `Ledger`, and the whole path runs with no key and no
network — the same discipline as every prior week.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — only run_stack.py and the older reasoning demos need it
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

No new dependency today — the whole stack is week-10 code you already have. `uv sync` pulls
in `pydantic-ai` (from Day 4) automatically.

## Run

```bash
uv run python run_typed.py        # Week 10 Day 4: the framework produces the triage contract from output_type
uv run python run_hooks.py        # Week 10 Day 3: a guard before a tool, an audit after it
uv run python run_subagent.py     # Week 10 Day 3: delegate a scoped question, get a contract back
uv run python run_mcp_server.py   # Week 10 Day 2: a client calls ScoutBot's own tools, served over MCP
uv run python run_mcp.py          # Week 10 Day 1: the model calls an order-status tool served over MCP
uv run python main.py             # Week 7's loop, unchanged
uv run pytest                     # the full suite, passing, before you change anything
```
