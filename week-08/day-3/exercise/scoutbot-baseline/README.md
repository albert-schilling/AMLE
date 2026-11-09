# ScoutBot — Week 8 Day 3 Starting Point

This is where today starts: Week 8 Day 2's finished graph, unchanged. Everything from Week 7 is
still here, plus Monday's explicit state and Tuesday's two additions, a conditional edge and a
checkpointer.

What you have:

- `src/scoutbot/graph.py` — `TicketState` declares what one run knows; four nodes;
  `route_after_triage()` reads the triage result and returns a node name, wired in with
  `add_conditional_edges()`; `build_ticket_graph(checkpointer=None)` takes an optional checkpointer,
  with `sqlite_checkpointer()` and `thread_config()` as helpers for the file-backed case.
- `run_graph.py` — every sample ticket through the graph, printing each node's update and the merged
  state after it.
- `run_resume.py` — Tuesday's crash-and-resume demo. `uv run python run_resume.py --crash` kills the
  process mid-run; `uv run python run_resume.py` finishes the same run from a new one.
- `src/scoutbot/core.py`, `tools.py`, `schema.py`, `loop.py`, `telemetry.py` — Week 7, untouched.
  Every model call goes through the Anthropic SDK directly. There is no LangChain chat model
  anywhere in here, which matters more today than it has so far.
- `tests/` — 49 passing tests. **Some of them will start failing today, and that is expected.**
  Several assert that a high-priority ticket runs all the way to a finished `resolution`. Once
  `escalate` pauses instead of finishing, those assertions are describing the old behaviour. Updating
  them is part of the work, not an accident.

## Two things worth noticing before you start

**`escalate_node` does not actually wait for anyone.** It writes `awaiting_human: True` into state
and the run ends. Read it: it is a note *about* a human, not a pause *for* one. Nothing is holding
the ticket, and nobody is going to be asked anything.

**A run tells you nothing while it happens.** Run `uv run python run_graph.py` and watch: several seconds
of silence per ticket, then output. The state is printed after each node because `stream()` is
already being used, but the work *inside* a node is invisible.

Both are today's exercise.

## Setup

```bash
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

`langgraph` and `langgraph-checkpoint-sqlite` are both already installed by that command. Today
needs nothing new: everything you are about to use ships inside `langgraph` itself.

## Run

```bash
uv run python run_graph.py                                           # the graph, ticket by ticket
uv run python run_resume.py --crash && uv run python run_resume.py   # Tuesday's crash and resume
uv run python main.py                                                # Week 7's ReAct loop, unchanged
uv run pytest                                                        # 49 tests, all passing right now
```

`run_resume.py` writes `checkpoints.db` next to itself (gitignored, along with SQLite's `-wal` and
`-shm` companions). Its `--crash` phase deletes and recreates it, so the demo is repeatable.
