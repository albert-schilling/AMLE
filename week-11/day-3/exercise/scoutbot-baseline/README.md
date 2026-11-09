# ScoutBot — Week 11 Day 3 Starting Point

This is where today starts: **the finished Day 2 team.** ScoutBot is now a **planning team** — a
model-backed planner reads a ticket, decides the ordered list of specialists it needs, and hands that
`plan` to the supervisor, which consults each worker (refund, order, research) in turn. Every model call
is metered, and model tiering keeps the bill down.

It works. But there is a question every day so far has quietly dodged:

> **How do you actually know it's any good — and how would you know if a change made it worse?**

"It looked fine when I tried a few tickets" does not scale. Today you make quality **measurable**: you
build an **eval** — a fixed set of cases scored by metrics you can rerun on every change — and you learn
when a check should be a cheap deterministic rule and when it needs an **LLM-as-judge**.

Two things to build, both new modules on top of this baseline:

1. **An eval harness** (`evals.py`) — a small labelled dataset, plus **deterministic metrics** (did the
   ticket reach the right specialist? did a grounded answer cite a source?) that touch no model. An eval
   **leads** with these: they are free, instant, and unarguable.
2. **An LLM-as-judge** (`judge.py`) — for the open-ended part a regex can't settle ("is this a *good*
   reply?"), a model scores the answer against a rubric. The judge is a **swappable model**, faked offline
   in tests exactly like every other model call in this codebase.

## What you have

- `src/scoutbot/orchestrator.py` — the team: `TeamState`, the orchestrator/supervisor nodes, the router,
  and the three `investigate -> respond` worker subgraphs. **The thing you evaluate.** Note the
  transcript logs `dispatch->refund`, which is how you read back *which specialist actually handled a
  ticket* — the raw material for a routing metric.
- `src/scoutbot/planner.py` — Day 2's model-backed planner (`plan_ticket`). The `_client` seam it patches
  in tests is the same one your judge will use.
- `src/scoutbot/metering.py` — Day 2's `Meter`/`cost_of`. Judging costs a model call too, so you meter it.
- `src/scoutbot/knowledge.py` — `format_passages` emits citations as `[refunds] ...`; that bracketed tag
  is exactly what a "cites sources" metric looks for.
- `tests/test_planner.py`, `tests/test_orchestrator.py` — the offline-with-stubs habit today copies.

## Three things worth knowing before you start

**1. Lead with deterministic checks.** Most regressions — a mis-route, a missing citation — are
properties of the output a string comparison can settle. Those metrics are free and never flaky, so run
them first and only escalate to a judge for what they genuinely cannot answer.

**2. The judge is just another model behind a seam.** deepeval lets you pass any `DeepEvalBaseLLM` as the
judge. You'll wrap your own Anthropic client for real runs and a canned `StubJudge` for tests — the exact
`_client`-patching discipline you've used since Week 7. No magic, no hosted service.

**3. deepeval runs fully offline — if you set it up right.** It phones home on import unless three env
vars are set *first*, and `GEval` scores on a 0–10 scale (it divides by 10). Both are handled for you in
the reference solution; the exercise calls them out so they don't bite you.

## Setup

```bash
cp .env.example .env         # ANTHROPIC_API_KEY — only run_judge.py (the real judge) needs it
uv sync                      # creates .venv/ and installs the locked dependencies, pytest included
uv add "deepeval>=4.1,<5"    # STEP 1 of today: the one new dependency of the whole week
```

**One new dependency today: `deepeval`.** It is not in this baseline's `pyproject.toml` on purpose —
adding it is the first thing today's exercise asks you to do. Everything else (the team, the planner, the
meter) you already have.

## Run

```bash
uv run python run_orchestrator.py   # the team, three tickets routed to three specialists (no key)
uv run python run_cost.py           # Day 2: the cost + tiering lever, offline
uv run pytest                       # the Day 1 + Day 2 + Week 10 suite, green, before you change anything
```
