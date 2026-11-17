# W8D2 Exercise — Route the Ticket, Then Survive the Restart

## Scenario

Same refund ticket, same 4:50pm on a Friday. Yesterday you made the run's facts explicit, and then
answered "no" to the only question Dana actually cares about: would that ticket survive the box
being restarted on Saturday morning?

Today it does. Two things have to happen first. The graph needs to be able to *act* on what triage
decided, instead of treating an urgent refund exactly like a password reset. And the run's facts
need to be written somewhere that outlives the process holding them.

By the end of the session you will kill a run halfway through, on purpose, and finish it from a
different `python` invocation without paying for the triage call twice.

## Starting point

`scoutbot-baseline/` is Week 8 Day 1's reference solution: Week 7's loop untouched, plus yesterday's
two-node graph. **Everyone extends this same baseline today, in place.** Three things to know:

- **`langgraph` is already installed. The SQLite checkpointer is not.** Adding it is one of the
  steps below, deliberately.
- **`loop.py` still doesn't change**, and `uv run python main.py` should still work when you're done.
- Run `uv run python run_graph.py` once before you start. That is today's "before".

## Your task

Working in pairs, on a new branch, extending `scoutbot-baseline/` in place:

### Part 1 — Let the graph choose (conditional routing)

1. **Write a router**: a plain function that takes the state and returns the *name* of the node that
   should run next, deciding from the triage result already in state. High priority means a person
   needs to see it; everything else ScoutBot handles itself. It takes state and returns a string,
   nothing more, so no model call and no graph is involved in deciding.
2. **Add the two nodes it chooses between.** One records that the ticket is waiting for a human, one
   records that it was handled. Keep both simple: a field written into state and a note appended is
   enough. Do **not** call `escalate_to_human` from Week 7 here; its blocking approval prompt is
   Wednesday's problem, not today's.
3. **Wire the branch** with `add_conditional_edges()`, passing an explicit map from what your router
   returns to the node it means. Both new nodes then lead to `END`.
4. **Test both branches offline, with no mocking at all.** Your router is a plain function of a
   hand-made state dict, so you can call it directly with a fake triage result and assert on the
   string it returns. If that feels too easy, that is the lesson.

### Part 2 — Let the run survive (checkpointing)

5. **Add the dependency**: `uv add "langgraph-checkpoint-sqlite>=3.1,<4"`. It lands pinned in
   `pyproject.toml` and `uv.lock`, and is installed into `.venv/`, in one step.
6. **Pass a checkpointer to `compile()`** and give your run a `thread_id`. Start with
   `InMemorySaver`, which needs no new dependency, and pass
   `config={"configurable": {"thread_id": "<the ticket id>"}}` when you invoke. Then use
   `graph.get_state(config)` to look at the run afterwards, and notice what `.next` tells you.
7. **Switch to a file-backed saver** (`SqliteSaver`, over a `sqlite3` connection opened with
   `check_same_thread=False`) so the state lands in a file rather than in this process.
8. **Kill a run and finish it from a new process.** Have the run die after triage but before the
   final node, then start `python` again and finish it with `graph.invoke(None, config)` and the
   same `thread_id`. Two details matter:
   - Pass `durability="sync"` to `invoke()` or `stream()`. The default writes checkpoints while the
     next step is already running, which is not enough to survive an abrupt kill. This is the one
     thing today that you would not guess.
   - Pass `None`, not your initial state. Passing state again starts a *new* run on top of the old
     one, and because your accumulating field has a reducer, it will look like it half-worked.
9. **Show that the model was not called again** on the resumed run. Whatever evidence convinces
   you: the streamed updates, a print inside the triage node, a counter.
10. **Same habit as every day**: commit on your branch, open a PR back to main.

## Expected outcome (minimum requirements)

- [ ] **A router**: a plain function from state to a node name, deciding from the triage result
- [ ] **Two terminal nodes**, one per branch, each writing its own outcome into state
- [ ] **A conditional edge** wired with `add_conditional_edges()` and an explicit path map
- [ ] **Both branches exercised**: an urgent ticket and an ordinary one take different routes, and
  you can show it
- [ ] **A checkpointer passed to `compile()`**, with a `thread_id` chosen deliberately
- [ ] **A resumed run**: killed mid-run, then finished by a *different* `python` process using
  `invoke(None, config)`
- [ ] **Evidence triage did not re-run** on the resumed run
- [ ] At least one passing test for the router, with yesterday's and Week 7's tests still passing
- [ ] `loop.py` unchanged, and `uv run python main.py` still works
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Add a second branch**, this time after the customer lookup: a ticket for a customer who isn't in
  the database arguably shouldn't be auto-resolved at all. Decide where it should go, and notice
  that the graph now has two independent decisions in it.
- **Run the same ticket twice on the same `thread_id`**, after it has already finished, and work out
  what happened from `get_state_history()`. Then run it on a fresh `thread_id` and compare.
- **Break it on purpose**: set `durability="async"` (the default) and kill the run a few times at
  the same point. Note what you lose, and how it differs between attempts. That variability is the
  whole reason the mode exists.
- **Ask what happens to work a node did before it crashed.** Put a `print` at the very top of the
  node you kill, resume, and count how many times it appears. Don't fix it. Thursday is about
  exactly that.

## If you're running out of time

Protect the two things the day is actually assessed on: the conditional edge (Part 1, steps 1-3) and
a run resumed in a second process (Part 2, steps 5-8). The router test in step 4 and the
`InMemorySaver` warm-up in step 6 are the first things to drop, and going straight to `SqliteSaver`
is fine if you're short. Flag whatever you skipped rather than quietly leaving it out.
(Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
