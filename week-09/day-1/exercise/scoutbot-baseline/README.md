# ScoutBot — Week 9 Day 1 Starting Point

This is where today starts: Week 8's finished agent, unchanged. Everything from Week 7 is still here,
plus Monday's explicit state, Tuesday's conditional edge and checkpointer, Wednesday's streamed draft
and real pause, Thursday's approval policy and send-once ledger, and Friday's offline tracing. What it
has never had is **knowledge it can look things up in** — every reply is written from the ticket text
and the model's own memory, with nothing to ground it in your actual policies. Today builds the first
half of that: retrieval.

What you have:

- `src/scoutbot/graph.py` — `TicketState` and the routed, pausing, retrying, ledgered graph.
  `draft_reply_node` writes the reply today from the ticket alone; by tomorrow it will be grounded in
  retrieved policy, but today you do not touch the graph at all.
- `src/scoutbot/core.py` — the Anthropic calls (`triage`, `stream_reply`). Every model call goes
  through the SDK directly; there is no LangChain in the stack, and today adds none.
- `src/scoutbot/policy.py`, `notify.py`, `tracing.py` — Thursday's policy and ledger, Friday's tracer.
- `run_approval.py`, `run_traced.py`, `run_events.py`, `run_resume.py`, `run_graph.py` — the Week 8
  demos, all still working.
- `src/scoutbot/loop.py`, `tools.py`, `schema.py`, `telemetry.py` — Week 7, untouched.
- `tests/` — the Week 8 suite, all passing. Today's job is to *add* a new module beside them, not to
  change any of it.

## Three things worth knowing before you start

**1. Anthropic has no embeddings API.** The model you have been calling all along cannot turn text into
a vector for you. Today's one new dependency, `fastembed`, is what does — and it runs on ONNX Runtime,
so it pulls no PyTorch and installs cleanly across machines.

**2. You already have a vector store, you just have not used it as one.** The SQLite file the
checkpointer writes to can hold a `BLOB` column just as easily as a checkpoint. A vector is
`float32` bytes; a "vector store" today is a table with a `vec BLOB` column and a cosine search in
numpy. No vector database, no SQLite extension.

**3. The embedder is the only thing that needs the network, so make it injectable.** Pass the embed
function into your knowledge base rather than importing a model inside it. In real use it is
`fastembed`; in a test it is three lines returning fixed vectors, and your ranking logic is then
testable with no download at all — the same trick that keeps every node in this repo callable without
an API key.

## Setup

```bash
cp .env.example .env                              # ANTHROPIC_API_KEY is still here for the rest of the repo; today needs no model call
uv sync                                           # creates .venv/ and installs the locked dependencies, pytest included
uv add "fastembed>=0.8,<0.9" "numpy>=1.26,<3"   # today's new dependencies; the first embedding fetch downloads a ~130MB model once
```

## Run

```bash
uv run python run_traced.py     # Week 8 Friday: trace a run, read it back
uv run python run_approval.py   # Week 8 Thursday: policy, pause, send once
uv run python main.py           # Week 7's loop, unchanged
uv run pytest                   # the Week 8 suite, passing, before you change anything
```
