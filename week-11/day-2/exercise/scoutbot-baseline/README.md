# ScoutBot — Week 11 Day 2 Starting Point

This is where today starts: **the finished Day 1 team.** Yesterday you split the ScoutBot monolith into an
**orchestrator** (or a **supervisor**) routing tickets to three specialist worker subgraphs — refund,
order, research. It works, but two things are still crude, and nobody is watching the bill:

- the dispatcher is a **keyword rule** (`classify_specialty`), so *"how long do refunds take?"* mis-routes
  to the refund worker when it is really a policy question; and
- the supervisor's **`plan` is seeded by hand** (`initial_state(..., plan=["research", "refund"])`) — the
  team has no way to decide a multi-step plan for itself.

Today you fix both, and you learn to **measure and cut what the team costs.**

```
START -> look_up_customer -> planner -> supervisor <-> (refund | order | research) -> END
```

Two things to build, both new modules on top of this baseline:

1. **A model-backed planner** (`planner.py`) — reads a ticket and returns the *ordered list of
   specialists* it needs. That list is exactly the `plan` your Day 1 `supervisor_node` already executes,
   so the planner slots in front of the supervisor and replaces the hand-seeded plan.
2. **Cost + latency metering** (`metering.py`) — read `response.usage`, price it against a small table,
   time calls with `perf_counter`, and pull the headline lever: **model tiering** (a cheap model plans and
   handles easy tickets, a strong one is spent only on the hard ones).

## What you have

- `src/scoutbot/orchestrator.py` — Day 1's team: `TeamState`/`WorkerState`, the orchestrator nodes and
  router, the three `investigate -> respond` worker subgraphs, `build_orchestrator`, and — the piece today
  builds on — **`supervisor_node`** (a hub that loops over a `plan`) and `build_supervisor`.
- `src/scoutbot/core.py` — the model-call boundary. Read how `triage` forces a single tool call and how
  tests patch `scoutbot.core._client`; your planner uses the *same* seam (a `make_plan` tool call, patched
  in tests).
- `src/scoutbot/tracing.py` — Week 8 Day 5's spans already time each node. Cost is the missing dimension:
  latency you have, dollars you do not.
- `tests/test_orchestrator.py` — the Day 1 team tested offline with stubs. Today's tests copy the habit.

## Three things worth knowing before you start

**1. The planner is just a smarter dispatcher.** Day 1's `classify_specialty` returned one specialty from
keywords; the planner returns an *ordered list* from the model. Same job — decide what the team does — one
rung smarter. Its output feeds the supervisor you already built.

**2. Cost needs no new tooling.** Every Anthropic reply carries a `usage` object (`response.usage`) with
`input_tokens`/`output_tokens`. Cost is `tokens x price` against a table you keep. Latency is
`time.perf_counter()` around the call. No dependency, no service.

**3. Model choice is the biggest lever.** Tiering — Haiku for the routine work, Sonnet only for the hard
tickets — is a one-line model-name swap given the `ANTHROPIC_MODEL` env convention, and it is where the
real savings are. Reach for it before you reach for a cleverer prompt.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — today's planner is a real model call, so the demo needs it
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

**No new dependency today.** Planning is one more model call through the SDK you already have; cost is
arithmetic. (Unlike Day 1, whose demo ran with no key, today's `run_planner.py` calls the model — but the
cost lever stays runnable offline, and every test stays offline.)

## Run

```bash
uv run python run_orchestrator.py   # Day 1: three tickets routed to three specialists (no key)
uv run python run_stack.py          # Week 10 Day 5: one agent, one ticket — classify, then resolve
uv run python run_graph.py          # Week 8/9: the monolithic ticket graph, streamed
uv run pytest                       # the Day 1 + Week 10 suite, passing, before you change anything
```
