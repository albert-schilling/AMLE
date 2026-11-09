# W8D5 Exercise — Make the Run Say What It Did

## Scenario

By the end of Thursday your graph does everything the week set out to build: it reads state, routes on
a policy, streams a draft, stops for the right human, survives a restart, and sends exactly one email.
Now run it once and try to answer two plain questions an on-call engineer would actually ask.

*Which node just took the longest?* You watched the whole run scroll past and you cannot say. The
`notes` field is a teaching aid, the `print()`s are gone, and the stream events died with the loop
that read them. *A ticket paused on Tuesday and finished on Saturday — what did it do, and when?* Same
answer: nothing was written down in a form you can query. The run said some of it out loud while it
worked and then forgot all of it.

Today you fix that. In the first half you make the run **emit a trace**: every node becomes a timed,
named span, all of them under one trace, exported to your terminal and a local file — no account, no
backend, no network. In the second half you **read a run back** after it is over, from durable records,
without re-running it. Along the way you will hit the honest limit that ties this day to the rest of
the week, and it is the point rather than a footnote.

## Starting point

`scoutbot-baseline/` is Week 8 Day 4's reference solution, unchanged: the policy, the pause for the
named approver, the retry, the send-once ledger, and Week 7's untouched loop. **Everyone extends this
same baseline today, in place.** Four things to know:

- **One thing to install**, and it is the first new dependency since Tuesday: `uv add
  "opentelemetry-sdk>=1.44,<2"`. The SDK only — you will *not* install an OTLP exporter, because nothing today
  talks to a backend. (`opentelemetry-api` comes along with the SDK.)
- **The graph does not change shape.** You are *instrumenting* Thursday's graph, not re-wiring it.
  Every node body stays exactly as it is.
- **Tracing must be opt-in.** When it is off, the graph must behave — and test — exactly as it did
  yesterday. If Thursday's tests start failing, tracing is not as opt-in as you think.
- **`loop.py` still doesn't change**, and `uv run python main.py` should still work when you're done.

## Your task

Working in pairs, on a new branch, extending `scoutbot-baseline/` in place:

### Part 1 — Emit a trace (OpenTelemetry, offline)

1. **Set up a tracer that goes nowhere off the machine.** Write a small `tracing.py`. Build an SDK
   `TracerProvider`, and give it a `ConsoleSpanExporter` (ships with the SDK) and a *local file*
   exporter you write yourself — one JSON object per finished span, appended to a `.jsonl` file. Wrap
   each in a `SimpleSpanProcessor` so spans export the instant they end. No endpoint, no OTLP, no
   account anywhere. Tip: do **not** call `trace.set_tracer_provider()` — that global can only be set
   once and will fight you across runs and tests; keep your provider local and hand your tracer to
   whoever needs it.
2. **Make each node a span, without touching the node.** Write a wrapper that takes a node callable
   and returns one that opens a child span on entry (name it after the node), records the node name, a
   status, and re-raises anything the node raises. Apply it at the graph builder, so node *bodies* are
   untouched and still plain functions a test can call with a dict. **Watch the injection:**
   `draft_reply` gets a `writer` injected by name — if your wrapper hides the signature, streaming
   silently stops. Make the wrapper signature-preserving and prove the draft still streams.
3. **Give every span the run's identity.** Stamp each span with a stable id read from state — the
   `ticket_id` is the obvious choice, since it is already the `thread_id`. Write down why you are doing
   this now; Part 2 is where it earns its place.
4. **Discover the orphaned-span claim for yourself, and check whether it is true here.** The
   documented trap is that OpenTelemetry's active span lives in a `contextvars.ContextVar` and each
   node runs in a fresh frame, so node spans supposedly orphan into separate traces. Run your traced
   graph and *look at the trace ids*. Do your node spans share one trace, or many? Do not take the
   blog's word or ours — measure it, and be ready to say what you found and why.
5. **Get to one trace per run.** Whatever you found in step 4, make the run produce a single trace by
   opening a **root span** around the `invoke()`/`stream()` call, keyed with the same run id. Then
   *remove* the root span and run again. Count the traces. That before/after is the reason the root
   span exists; keep both observations.
6. **Do not paint a pause red.** Trace a run that pauses (the €900 refund). Look at the paused node's
   span status. `interrupt()` raises to signal the pause — if your wrapper treats that like any other
   exception, the span reads ERROR and the trace says "escalate crashed", which is a lie. Catch the
   pause signal specifically, mark it as an interrupt rather than a failure, and re-raise so the pause
   still happens. (Look at what `interrupt()` actually raises.)
7. **Confirm timing is real.** In your trace, `draft_reply` (a model call) should dwarf `check_policy`
   (a dict lookup). Note how this differs from Week 7 Day 5's loop logger, where every step in one API
   turn shared a single turn-level duration.

### Part 2 — Read a run back (the durable records, and the honest limit)

8. **Query the trace instead of re-running it.** Write a `read_spans()` that reads your JSONL file
   back, and use it to answer step-4's question in code: *which node was slowest on that run?* You must
   not invoke the graph to answer it. This is the whole point of a trace — a question answered after
   the run is over.
9. **Recover the timeline with no instrumentation at all.** Call `graph.get_state_history(config)` on
   a finished run and walk what it gives you: each snapshot's `step`, its `next`, and its state. Notice
   it needed no tracing — Tuesday's checkpointer was already writing it. What does `next` equal on the
   newest snapshot of a *finished* run?
10. **Read a run back from a *different process*.** In one script run a ticket to a finished state;
    in a *separate* `python` invocation, open the graph on the same SQLite file and call
    `get_state_history()` for that thread. It should reconstruct the whole run without re-running
    anything. Do the same for a run you leave *paused*: what does the newest snapshot's `next` tell you
    about the node that still owes work?
11. **Now find the limit, on purpose.** Trace a run that pauses in one process and resumes in another
    (two `python` invocations, or two separate tracers standing in for two processes). Group your saved
    spans by trace id. **How many traces did one logical run produce?** Work out why OpenTelemetry has
    nothing that stitches them together, and what — of everything you have built this week — actually
    ties the pieces into one story. Write that answer down; it is the day's second half in one sentence.
12. **Say what each record is for.** In a sentence each: what can the saved spans answer that
    `get_state_history()` cannot, and what can the checkpoint history answer that the spans cannot?
    (Hint: one is per-process and stops at a pause; one is durable and crosses it.)
13. **Write tests, offline.** Capture *real* spans in memory (an in-memory exporter is a few lines) and
    assert: the JSONL round-trips through `read_spans`; the wrapper keeps `writer` injection; a failing
    node's span is ERROR and the exception still propagates; a paused node's span is *not* ERROR; one
    root span yields one trace and no root span yields one-trace-per-node; two runs under one id land in
    two traces but one id. No model call in any of them.
14. **Same habit as every day**: commit on your branch, open a PR back to main. Confirm Thursday's
    tests still pass untouched — if they don't, your tracing is not opt-in.

## Expected outcome (minimum requirements)

- [ ] **`opentelemetry-sdk` installed**, and *no* OTLP/exporter-backend dependency added
- [ ] **A tracer that exports only to the console and a local JSONL file** — no endpoint, no account,
  no network
- [ ] **Each node is a span under one trace per run**, with node bodies untouched and `draft_reply`
  still streaming (signature-preserving wrapper)
- [ ] **Every span carries a stable run id** read from state
- [ ] **A written finding on the orphaned-span claim** for *this* graph: measured, not assumed
- [ ] **A root span makes one trace; removing it makes one-trace-per-node** — both observed
- [ ] **A paused node's span is not marked ERROR**, and the pause still works
- [ ] **`read_spans()` answers "which node was slowest" without re-running the graph**
- [ ] **`get_state_history()` reconstructs a finished run and a paused run from a separate process**
- [ ] **A paused-then-resumed run shows more than one trace**, and a written sentence naming what ties
  them together
- [ ] **Offline tests** covering the round-trip, the wrapper, the error/pause statuses, the root-span
  behaviour, and the two-traces-one-id case — none calling a model
- [ ] Thursday's existing tests still pass, untouched (tracing is opt-in)
- [ ] `loop.py` unchanged, and `uv run python main.py` still works
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Point it at something real (then take it back out).** Add `opentelemetry-exporter-otlp` and a
  second processor pointing at a local Jaeger or Tempo in Docker, and see your spans in a real UI.
  Notice how little changed: one exporter, one line. That "one line" is the entire distance between
  offline and hosted, and the reason the day teaches the vendor-neutral core.
- **Reassemble the tree from the file alone.** Your span records carry `trace_id`, `span_id` and
  `parent_id`. Using only the JSONL, print the run as an indented tree (root span, node spans beneath
  it). You have just reimplemented the least glamorous 10% of a tracing UI.
- **Correlate the two halves of a paused run.** Take the paused-then-resumed run from step 11 and, from
  the saved spans plus `get_state_history()`, produce a single reconstructed story of the whole ticket:
  what happened, in order, across both processes, tied by the id. This is what an on-call engineer
  actually does.
- **Add one attribute that would have saved you an incident.** Pick a single extra span attribute
  (the approver required? the retry attempt number? the policy reason?) that would make a real
  production trace more answerable, add it, and justify why that one and not ten others.
- **Trace the retry.** Run the `--flaky` send under your tracer and look at `send_reply`: how many
  spans, and what do their statuses say? Confirm the trace shows a node that ran three times, and that
  the ledger still let exactly one email out.

## If you're running out of time

Protect Part 1 steps 1–5 and Part 2 steps 8 and 11. A tracer, node spans under one root, reading the
slowest node back from the file, and *seeing* that a paused run makes two traces tied by one id — that
arc is what the day is assessed on. The offline test suite (step 13) is the first thing to trim to a
couple of cases, then step 6's pause-status refinement, then the separate-process reads in step 10 (do
them in one process and say so). Do **not** trim step 11: the two-traces-one-id observation is the
whole reason today belongs to this week. Flag whatever you skipped rather than quietly leaving it out.
(Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
