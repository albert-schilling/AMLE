# W8D1 Exercise — Make ScoutBot's State Explicit

## Scenario

Dana read your Week 7 memo and approved the LangGraph spike. Her first test case is unglamorous:
a refund ticket escalates at 4:50pm on a Friday, nobody approves it before the weekend, and the
box gets restarted on Saturday morning. Week 7's ScoutBot loses that run completely — not because
the model did anything wrong, but because everything it had figured out lived in local variables
that no longer exist.

Surviving that restart is tomorrow's job. Today is the part that has to come first: getting a
run's facts out of local variables and into one declared place, where something other than this
one Python process could eventually read them.

## Starting point

`scoutbot-baseline/` is Week 7 Day 5's reference solution, unchanged: the bounded ReAct loop, both
client tools, both server tools, and the JSONL step logger. **Everyone extends this same baseline
today, in place.** Two things to know before you start:

- **LangGraph isn't installed yet.** Adding it is step 1, deliberately.
- **`loop.py` doesn't change today.** You're adding a second path through the same repo, not
  replacing the first one. Both should still run when you're done.

Open `src/scoutbot/loop.py` first and find where it keeps each thing it knows: the ticket text,
the customer record it looked up, the observations, the step count. That's the "before" you're
about to make explicit.

## Your task

Working in pairs, on a new branch, extending `scoutbot-baseline/` in place:

1. **Add the dependency**: `uv add "langgraph>=1.2,<2"`. One command pins it in `pyproject.toml`,
   updates `uv.lock`, and installs it into `.venv/`.
2. **Declare a state schema** in a new `src/scoutbot/graph.py`: a `TypedDict` naming what one
   ticket run accumulates. At least one field must **accumulate** across nodes (a list that grows,
   using a reducer) and at least one must be **replaced** by whoever writes last. Be able to say
   which is which and why.
3. **Write two nodes** as plain functions, each taking the state and returning **only the fields
   it changed**, not a whole new state. One looks the customer up (reuse `look_up_customer`), one
   triages the ticket (reuse `triage`). Neither should call the other.
4. **Wire and compile the graph**: `START → look_up_customer → triage_ticket → END`.
5. **Make the second node read what the first one wrote.** The triage decision must be built from
   what's in state, including the looked-up customer record, not from the ticket text alone. If
   your triage node would behave identically with the first node deleted, the state isn't doing
   any work yet.
6. **Run it and watch state change**: print what each node returned, or the whole state after each
   node, so you can see the accumulating field grow while the replaced one doesn't.
7. **One test, offline**, mocking the model the same way every earlier day does.
8. **Same habit as every day**: commit on your branch, open a PR back to main.

## Expected outcome (minimum requirements)

- [ ] **State schema**: a `TypedDict` declaring the fields one ticket run accumulates
- [ ] **A reducer**: at least one field that accumulates across nodes, plus at least one plain
  field that gets replaced, and you can explain the difference out loud
- [ ] **Two nodes**: each returns only the fields it changed
- [ ] **A compiled graph**: `START → look_up_customer → triage_ticket → END`, running end to end on
  a real ticket
- [ ] **State doing real work**: the triage decision reflects the customer record the first node
  wrote
- [ ] **Visible state**: you can show what each node changed, not just the final answer
- [ ] At least one passing test for the graph, with Week 7's existing tests still passing untouched
- [ ] `loop.py` unchanged, and `uv run python main.py` still works
- [ ] Work is on a branch with an open pull request

## If you finish early

- Add one more field to your state that today's graph doesn't strictly need but a support team
  would want later (who last touched the ticket, say, or every customer id seen). Decide whether
  it needs a reducer, and be ready to justify the choice.
- Delete the reducer annotation from your accumulating field, run it again, and watch what happens
  to the earlier node's contribution. Put it back. That failure mode is much easier to recognise
  once you've caused it on purpose.
- Look up what `compile()` accepts and work out, out loud with your pair, what you'd hand it to
  make a run survive a restart. Don't build it — that's tomorrow, and guessing the name of the
  argument is the useful part.

## If you're running out of time

It's fine to stop once the graph runs end to end with a declared state schema and two nodes, even
if you haven't written the test or gotten the triage node reading the customer record yet — flag
which of those is missing rather than quietly skipping it. The one thing worth protecting is the
reducer versus plain-field distinction in step 2: that's the point of the day, not the graph
mechanics around it.
(Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
