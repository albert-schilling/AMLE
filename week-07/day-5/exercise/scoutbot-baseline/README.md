# ScoutBot (Day 5 starting point)

This is Day 4's reference solution — a working, tested ReAct loop with two client tools
(`look_up_customer`, `escalate_to_human`) and two server tools (`web_fetch`,
`code_execution`), plus Day 1's `triage()` underneath. Everyone starts today from this same
known-good baseline, regardless of how far you got on your own Day 4 code. Nothing in here
changes today — you're adding to it, not rebuilding it.

- `src/scoutbot/core.py` / `schema.py` / `tools.py` — Day 1-2's triage logic and client
  tools, unchanged.
- `src/scoutbot/server_tools.py` — Day 4's two server tool definitions (`web_fetch`
  restricted to `status.stripe.com`, `code_execution`), unchanged.
- `src/scoutbot/loop.py` — Day 4's bounded ReAct loop, handling both client and server tool
  results, unchanged. Today's addition is a saved, structured record of what this loop
  already does — not a change to what it does.
- `mock_customers.json` / `sample_tickets.json` / `sample_app.log` — the same fake data as
  Day 4 (5 tickets: 3 from Day 2, plus `T-2001`/`T-2002` for `web_fetch`/`code_execution`).

**Your actual task is in [`../exercises.md`](../exercises.md)** — this folder is just the
starting point, not the instructions.

## Setup

```bash
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

## Run / test (as-is, before you change anything)

```bash
uv run python main.py   # runs Day 4's loop on all 5 sample tickets
uv run pytest           # Day 4's tests should all pass, untouched
```
