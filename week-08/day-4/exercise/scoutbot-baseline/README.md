# ScoutBot — Week 8 Day 4 Starting Point

This is where today starts: Week 8 Day 3's finished graph, unchanged. Everything from Week 7 is still
here, plus Monday's explicit state, Tuesday's conditional edge and checkpointer, and Wednesday's
streamed draft and real pause.

What you have:

- `src/scoutbot/graph.py` — `TicketState` declares what one run knows; five nodes;
  `route_after_triage()` reads the triage result and returns a node name; `escalate_node()` calls
  `interrupt()` and genuinely waits for a person; `draft_reply_node()` streams the reply out through
  an injected `writer` while it is still working; `build_ticket_graph()` defaults to an
  `InMemorySaver`, with `sqlite_checkpointer()` and `thread_config()` for the file-backed case.
- `run_events.py` — Wednesday's demo. `uv run python run_events.py` runs until a person is needed and exits;
  `uv run python run_events.py --approve` finishes the same run from a new process.
- `run_resume.py` — Tuesday's crash-and-resume demo.
- `run_graph.py` — every sample ticket through the graph, printing each node's update and the merged
  state after it.
- `src/scoutbot/core.py`, `tools.py`, `schema.py`, `loop.py`, `telemetry.py` — Week 7, untouched.
  Every model call goes through the Anthropic SDK directly.
- `tests/` — 61 passing tests. **Some of them will start failing today, and that is expected.**
  Several assert on `route_after_triage` and on the exact shape of the pause payload, both of which
  today changes. Updating them is part of the task.

Two things about the data are new, and they are deliberately given to you rather than left to build:

- `sample_tickets.json` now carries a **`refund_amount`** on every ticket. It is a billing fact,
  looked up alongside the ticket, not something a model reads out of the customer's message. A
  customer claiming they were charged nine hundred euros is a claim; the charge is a fact. Nothing in
  the code reads this field yet — wiring it through is step 1.
- `mock_customers.json` has a fourth customer, `1004`, with four refunds in the last ninety days.
  Their ticket is for twelve euros fifty. Keep that pair in mind when you write your policy: a good
  policy is not only a number.

## Three things worth knowing before you start

**1. A resumed node re-runs from its first line.** Wednesday established this. Whatever sits above
your `interrupt()` call happens again.

**2. A retried node does exactly the same thing**, and a retry is one argument to `add_node()`. You
will meet this today.

**3. Nothing in this repo sends anything to anybody yet.** `escalate_node` records an approval and
the run ends. Today it will actually send something, and then both facts above stop being trivia.

## Setup

```bash
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

Nothing new to install today: everything you need ships inside `langgraph` and the Python standard
library.

## Run

```bash
uv run python run_events.py && uv run python run_events.py --approve   # Wednesday: stream, pause, resume
uv run python run_resume.py --crash && uv run python run_resume.py     # Tuesday: crash and resume
uv run python run_graph.py                                             # every sample ticket, one after another
uv run python main.py                                                  # Week 7's loop, unchanged
uv run pytest                                                          # 61 passing, before you change anything
```
