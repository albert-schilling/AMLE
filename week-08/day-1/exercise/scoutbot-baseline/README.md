# ScoutBot (Week 8 Day 1 starting point)

This is Week 7 Day 5's reference solution — a working, tested ReAct loop with two client tools
(`look_up_customer`, `escalate_to_human`), two server tools (`web_fetch`, `code_execution`),
Day 1's `triage()` underneath, and JSONL step logging on top. Everyone starts this week from this
same known-good baseline, regardless of how far you got on your own Week 7 code. Nothing in here
changes today — you're adding to it, not rebuilding it, and `loop.py` in particular stays exactly
as it is.

- `src/scoutbot/core.py` / `schema.py` / `tools.py` — Week 7's triage logic and client tools.
- `src/scoutbot/server_tools.py` — Week 7 Day 4's two server tool definitions.
- `src/scoutbot/loop.py` — the bounded ReAct loop. Worth opening before you start: look at where
  it keeps the things it knows (the `messages` list, `steps`, each observation). That is today's
  subject.
- `src/scoutbot/telemetry.py` — Day 5's JSONL step logger.
- `mock_customers.json` / `sample_tickets.json` / `sample_app.log` — the same fake data as Week 7.

**LangGraph is not installed here yet.** Adding it is the first step of today's task, on purpose,
so the dependency lands in your own `pyproject.toml` rather than arriving pre-wired.

**Your actual task is in [`../exercises.md`](../exercises.md)** — this folder is just the starting
point, not the instructions.

## Setup

```bash
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

## Run / test (as-is, before you change anything)

```bash
uv run python main.py   # runs Week 7's loop on all 5 sample tickets
uv run pytest           # Week 7's 30 tests should all pass, untouched
```
