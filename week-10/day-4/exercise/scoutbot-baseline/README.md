# ScoutBot — Week 10 Day 4 Starting Point

This is where today starts: **your finished Week 10 Day 3 agent — hooks and a subagent.** By now ScoutBot
speaks MCP from both sides (client and server), guards its tool calls with pre- and post-hooks, issues an
idempotent refund, and can delegate a scoped policy question to a research subagent that must return a
validated `ResearchResult`. Every one of those pieces is tested offline.

Today you change how ScoutBot produces one small thing it has produced since Week 7: its **triage
result** — a `TicketTriage` with a category, a priority, and a suggested owner. In `core.triage` you
built that result the hard way: write the tool schema by hand from the Pydantic model, force the tool
call, dig the `tool_use` block out of the reply, `model_validate` it, and retry once in a `try/except`.
It works — but every line is *plumbing* wrapped around one tiny contract.

Today a framework owns that plumbing. You build a **Pydantic AI** agent whose `output_type=TicketTriage`,
and the framework derives the schema, validates the reply, and retries on a miss. Same contract, written
as one argument instead of a hand-rolled loop. And you keep it offline-testable the framework-native way:
build the agent with **no bound model** (so import needs no key), pass the model at call time, and drive
the tests with `TestModel`/`FunctionModel` under `ALLOW_MODEL_REQUESTS = False`.

What you have:

- `src/scoutbot/core.py` — **the contrast for today.** `core.triage` is the hand-rolled, contract-driven
  triage: `TRIAGE_TOOL` (schema from `TicketTriage.model_json_schema()`), a forced tool call, `model_validate`,
  and a retry-once wrapper that raises `TriageError`. Read it before you start; today's agent replaces its
  *machinery*, not its result.
- `src/scoutbot/schema.py` — **the contract, unchanged.** `TicketTriage` (and its `Category`/`Priority`
  enums) is the exact type today's agent will produce. You reuse it; you do not invent a new one.
- `src/scoutbot/hooks.py`, `subagent.py`, `mcp_server.py`, `mcp_client.py`, `loop.py`, `graph.py`,
  `memory.py`, … — the rest of the agent, untouched today.
- `tests/` — the full suite, all passing (`209`, with a couple of embed-gated skips). Today's tests add one
  file, `tests/test_typed_agent.py`, that drives the new agent with fake models and no network.

## Three things worth knowing before you start

**1. The contract already exists — you are changing the machinery, not the shape.** `typed_agent.triage`
must return the *same* `schema.TicketTriage` that `core.triage` returns. `output_type=TicketTriage` is the
whole difference: the framework generates the schema, validates the reply, and retries, where Week 7 wrote
each of those by hand.

**2. Build the agent with no bound model, or import needs a key.** Constructing `Agent(output_type=…)`
with **no** `model=` keeps `import scoutbot.typed_agent` key-free — and therefore lets every test import it
freely. Binding a provider string (`Agent("anthropic:…")`) infers the provider eagerly and requires
`ANTHROPIC_API_KEY` *at construction*. Put the real model behind a lazy factory and pass it at call time.

**3. Prove it offline with fake models and a hard backstop.** Tests pass `TestModel` (auto-valid, or
`custom_output_args` for exact values) and `FunctionModel` (a function you write, so you can script a
bad-then-good reply and watch the retry). Set `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` once at the
top of the test module, so any *real* request raises before it reaches the network. Same "mock the
collaborator" discipline as patching the Anthropic client — only the mechanism differs.

## Setup

```bash
cp .env.example .env            # ANTHROPIC_API_KEY — only run_typed.py and the older reasoning demos need it
uv sync                         # creates .venv/ and installs the locked dependencies, pytest included
uv add "pydantic-ai>=2.27,<3"   # NEW today — the baseline omits it on purpose (step 1 of the exercise)
```

`pydantic-ai` is today's one new dependency; the baseline `pyproject.toml` does not list it yet, so adding
it is your first task. `uv add` pins it there and in `uv.lock` for you.

## Run

```bash
uv run python run_hooks.py        # Week 10 Day 3: a guard before a tool, an audit after it
uv run python run_subagent.py     # Week 10 Day 3: delegate a scoped question, get a contract back
uv run python run_mcp_server.py   # Week 10 Day 2: a client calls ScoutBot's own tools, served over MCP
uv run python run_mcp.py          # Week 10 Day 1: the model calls an order-status tool served over MCP
uv run python run_router.py       # Week 9 Day 4: classify the ticket, then retrieve as hard as it deserves
uv run python main.py             # Week 7's loop, unchanged
uv run pytest                     # the full suite, passing, before you change anything
```
