# W8D3 Exercise — Make It Wait, and Make It Visible

## Scenario

The refund ticket routes to `escalate` now, and the run survives the box restarting. Read what
`escalate_node` actually does though: it writes `awaiting_human: True` into state and the run ends.
Nobody is asked anything. Nothing is waiting. Dana has wanted a reliable escalation since Week 7,
and what she has is a sticky note.

Today you make the run genuinely stop and wait for a person, and pick up later inside the very node
that asked. On the way you fix the other thing that makes a run hard to trust: it says nothing while
it works. A run is a stream of events, and once you can see the events, the pause is just one more of
them.

By the end of the session you will stop a run on purpose, exit the process, and finish it from a
different `python` invocation by handing it a human's answer.

## Starting point

`scoutbot-baseline/` is Week 8 Day 2's reference solution: Week 7's loop untouched, Monday's explicit
state, Tuesday's conditional edge and checkpointer. **Everyone extends this same baseline today, in
place.** Four things to know:

- **Nothing to install.** Everything you need ships inside `langgraph`, which arrived on Monday. This
  is the first day of the week with no new dependency.
- **Some existing tests will start failing, and that is expected.** Several assert that a
  high-priority ticket runs through to a finished `resolution`. Once `escalate` pauses instead,
  those assertions describe the old behaviour. Updating them is part of the task, not a mistake you
  made.
- **`loop.py` still doesn't change**, and `uv run python main.py` should still work when you're done.
- Run `uv run python run_graph.py` once before you start, and time how long each ticket is silent for. That
  is today's "before".

## Your task

Working in pairs, on a new branch, extending `scoutbot-baseline/` in place:

### Part 1 — Make the run visible (events)

1. **Watch what a run already emits.** Add `"custom"` to the stream modes you pass to `stream()`, so
   you are asking for `stream_mode=["updates", "custom"]`, and print the mode alongside each chunk.
   Nothing new will appear yet: no node emits a custom event. That empty result is the point of the
   step.
2. **Emit one event from inside a node.** Take any existing node and have it announce something while
   it works. Give the node a parameter named `writer`, annotated `StreamWriter` (from
   `langgraph.types`), and call `writer({"...": ...})` with any JSON-serialisable dict. LangGraph
   passes the real writer in when it runs your node. Give the parameter a default of a function that
   does nothing, so the node is still callable outside a graph.
   > You will also find `get_stream_writer()` in the docs, called inside the node body. It works, but
   > a node written that way can no longer be called as a plain function with a hand-made dict, which
   > is the property Monday made a virtue of. Try it if you like, and see the error.
3. **Confirm the ordering**, because it is the whole claim: your custom event arrives *before* the
   `updates` chunk for the node that emitted it. Output exists while the node is still working, not
   only once it has returned.

### Part 2 — Make it wait (interruption)

4. **Turn `escalate` into a real pause.** Import `interrupt` from `langgraph.types` and call it
   inside `escalate_node`, handing it a dict containing whatever a human would need in order to
   decide. Not just a ticket ID: if you had to answer this yourself from that payload alone, could
   you? Then run a high-priority ticket and look at what `invoke()` gives back, and at
   `graph.get_state(config).next`.
5. **Notice that a checkpointer is no longer optional.** Try the pause with no checkpointer at all
   and see what happens. It will surprise you: work out *when* the problem surfaces, rather than
   assuming it surfaces immediately.
6. **Resume it, from a second process.** Use the file-backed `SqliteSaver` from Tuesday so the pause
   outlives the process, let the first process exit while the run is paused, then in a new one call
   `graph.invoke(Command(resume=<the human's answer>), config)` with the same `thread_id`.
   `Command` comes from `langgraph.types`. Two things to watch for:
   - **Whatever you pass as `resume` is exactly what the `interrupt()` call returns** inside the
     node. LangGraph does not validate it. Print it from inside the node the first time.
   - **Passing your initial state instead of a `Command` does not resume anything.** If you want to
     see it, try it, then look at your accumulating field. Same mistake as Tuesday's, same shape.
7. **Show what re-ran and what didn't.** Put a `print` at the very top of the pausing node, and
   count the model calls in the resuming process. One of those numbers goes up on resume and the
   other does not. Write down which, and why.
8. **Write at least one test for the pause and the resume.** An `InMemorySaver` is enough, and no
   second process is needed: invoke, assert it paused where you expect, then invoke again with a
   `Command` and assert the run finished with the answer you gave it. Then fix the existing tests
   your change broke.
9. **Same habit as every day**: commit on your branch, open a PR back to main.

## Expected outcome (minimum requirements)

- [ ] **A run streamed with `"custom"` in its modes**, printing events as they arrive
- [ ] **At least one custom event emitted from inside a node**, via an injected `writer`
- [ ] **Evidence of the ordering**: your event arrives before that node's `updates` chunk
- [ ] **`escalate` calls `interrupt()`** with a payload a human could actually act on
- [ ] **A paused run that outlives its process**: the first process exits, the ticket is still there
- [ ] **A resumed run**: finished by a *different* `python` process with `Command(resume=...)`, where
  the value you passed is visibly what `interrupt()` returned inside the node
- [ ] **A note on what re-ran**: which nodes ran again on resume, which didn't, and why
- [ ] At least one passing test covering the pause and the resume
- [ ] The existing tests your change broke are updated, not deleted or skipped
- [ ] `loop.py` unchanged, and `uv run python main.py` still works
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Stream the model's own output.** Give `core.py` a streaming sibling to `triage()` using
  `client.messages.stream(...)`, have it hand each piece of text to a callback, and drive your
  `writer` from that callback in a node that drafts a reply. Watch the reply form on screen. Then
  measure it: how many pieces arrive, and how long before the first one? It is less token-by-token
  than you expect, and the granularity is the provider's choice, not yours.
- **Ask what a second `interrupt()` in the same node would do**, and try it. Then work out what your
  resume code would have to look like to answer two questions in order.
- **Make the pause do something irreversible.** Put a line above the `interrupt()` call that pretends
  to send an email (a `print` is enough), then resume, and count how many emails you sent. Don't fix
  it. Thursday is about exactly that, and this is the cheapest possible way to feel why.
- **Look at `get_state_history(config)`** on a thread you paused and resumed, and find the pause in
  it.

## If you're running out of time

Protect Part 2. The pause and the resume across two processes (steps 4, 6, 7) are what the day is
assessed on, and they are also what Thursday builds on. Steps 1-3 are the first to drop: if you have
to, take the coach's demo of the event stream as read and go straight to `interrupt()`. Step 5's
no-checkpointer experiment and step 8's test are next. Flag whatever you skipped rather than quietly
leaving it out. (Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
