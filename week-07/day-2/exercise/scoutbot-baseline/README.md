# ScoutBot (Day 2 starting point)

This is yesterday's reference solution — a working, tested `triage()` function, in a real
repo, using one Anthropic tool call and a Pydantic schema. Everyone starts today from this
same known-good baseline, regardless of how far you got on your own version yesterday.

- `src/scoutbot/schema.py` / `core.py` — yesterday's triage logic, unchanged.
- `mock_customers.json` — fake account data for the new `look_up_customer` tool you'll add
  today (no need to invent your own).
- `sample_tickets.json` — the same 3 tickets as yesterday, now each with a `customer_id`.

**Your actual task is in [`../exercises.md`](../exercises.md)** — this folder is just the
starting point, not the instructions.

## Setup

```bash
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

## Run / test (as-is, before you change anything)

```bash
uv run python main.py   # runs yesterday's triage() on all 3 sample tickets
uv run pytest           # yesterday's tests should all pass, untouched
```
