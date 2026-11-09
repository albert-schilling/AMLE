# ScoutBot — Week 8 Day 5 Starting Point

This is where today starts: Week 8 Day 4's finished graph, unchanged. Everything from Week 7 is still
here, plus Monday's explicit state, Tuesday's conditional edge and checkpointer, Wednesday's streamed
draft and real pause, and Thursday's approval policy, approver check, retry, and send-once ledger.

What you have:

- `src/scoutbot/graph.py` — `TicketState`; the routed, pausing, retrying graph. `check_policy_node`
  applies the policy and writes the decision into state; `route_on_approval` reads that decision;
  `escalate_node` names the required approver, pauses, and checks the answer; `send_reply_node` carries
  a `RetryPolicy` and both branches converge on it; `draft_reply_node` streams the reply through an
  injected `writer`. `build_ticket_graph()` defaults to an `InMemorySaver`, with `sqlite_checkpointer()`
  and `thread_config()` for the file-backed case.
- `src/scoutbot/policy.py` — the pure approval table (no model, no graph, no I/O).
- `src/scoutbot/notify.py` — `send_reply()` (the one irreversible thing) and the SQLite-backed
  `Ledger` that keeps it to once per ticket.
- `run_approval.py` — Thursday's demo: `uv run python run_approval.py`, `--approve`, `--approve-wrong-role`,
  `--flaky`.
- `run_events.py`, `run_resume.py`, `run_graph.py` — Wednesday's, Tuesday's, and the all-tickets demos.
- `src/scoutbot/core.py`, `tools.py`, `schema.py`, `loop.py`, `telemetry.py` — Week 7, untouched.
  Every model call goes through the Anthropic SDK directly. `telemetry.py` is Week 7 Day 5's JSONL
  *loop* logger — worth re-reading today, because today does the same idea for the *graph*, with a
  real library and per-node resolution.
- `tests/` — 106 passing tests. Today's job is to *add* tracing without breaking any of them: if a
  test here starts failing, your tracing is not opt-in enough.

## Three things worth knowing before you start

**1. Nothing here is queryable after the run.** `notes` is a teaching field, the `print()`s scroll
past, and the stream events die with the loop. Ask "which node was slowest?" and the graph cannot tell
you. That is the gap today closes.

**2. The checkpointer has been quietly recording a timeline all week.** `get_state_history(config)`
walks it, and you did not have to instrument anything for that to be true. Half of "read the run back"
is already sitting in the SQLite file.

**3. A resume is a new process.** Tuesday's crash-and-resume and Wednesday's pause-and-resume both
proved it. Keep it in mind when you trace a paused run — it is the reason a single run can end up with
more than one trace.

## Setup

```bash
cp .env.example .env                 # then fill in your real ANTHROPIC_API_KEY
uv sync                              # creates .venv/ and installs the locked dependencies, pytest included
uv add "opentelemetry-sdk>=1.44,<2"  # today's one new dependency, the first since Tuesday
```

The SDK only — you will not install any exporter that talks to a backend, because today exports to the
console and a local file and nowhere else.

## Run

```bash
uv run python run_approval.py && uv run python run_approval.py --approve   # Thursday: policy, pause, send once
uv run python run_events.py && uv run python run_events.py --approve       # Wednesday: stream, pause, resume
uv run python run_resume.py --crash && uv run python run_resume.py         # Tuesday: crash and resume
uv run python run_graph.py                                                 # every sample ticket, one after another
uv run python main.py                                                      # Week 7's loop, unchanged
uv run pytest                                                              # 106 passing, before you change anything
```
