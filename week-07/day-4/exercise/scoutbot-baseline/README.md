# ScoutBot (Day 4 starting point)

This is Day 2's reference solution — a working, tested ReAct loop with two client tools
(`look_up_customer`, `escalate_to_human`), plus Day 1's `triage()` underneath. Everyone starts
today from this same known-good baseline, regardless of how far you got on your own Day 2 code.
Nothing in here changes today — you're adding to it, not rebuilding it.

- `src/scoutbot/core.py` / `schema.py` — Day 1's triage logic, unchanged.
- `src/scoutbot/tools.py` / `loop.py` — Day 2's two client tools and the bounded ReAct loop,
  unchanged. Today's two new tools are *server* tools (Anthropic's own infrastructure runs
  them), which is a different shape from either of these — see the flipped material.
- `mock_customers.json` / `sample_tickets.json` — the same fake data as Day 2.

**Your actual task is in [`../exercises.md`](../exercises.md)** — this folder is just the
starting point, not the instructions.

## Setup

```bash
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

## Run / test (as-is, before you change anything)

```bash
uv run python main.py   # runs Day 2's loop on all 3 sample tickets
uv run pytest           # Day 2's tests should all pass, untouched
```
