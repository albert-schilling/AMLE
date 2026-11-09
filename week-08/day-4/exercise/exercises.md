# W8D4 Exercise — Decide Who Signs, and Send It Once

## Scenario

Wednesday's run stops and asks a person. Two things about that are still unfinished, and they are both
the kind of thing that only hurts after you ship.

Read the router. Which tickets need a human is one line: `priority == "high"`. So a twelve-euro
goodwill credit and a nine-hundred-euro refund on an account that has already had four refunds this
quarter take the same path, get the same anonymous "a human needs to look at this", and neither
payload says who is allowed to say yes. Dana, who owns the refund policy, cannot read that rule
anywhere, cannot change it without asking an engineer, and cannot tell whether it was followed.

Then read `escalate_node` to the end. The reply is approved and the run finishes. Nothing is ever
sent. The moment you fix that — and you will, today — the fact you proved on Wednesday stops being
trivia: a resumed node runs its first line twice, so an email above a pause goes out twice.

By the end of the session a policy someone non-technical could read will decide who has to approve
each refund, an approval from the wrong person will be refused, and the reply will go out exactly
once even when the node that sends it runs three times.

## Starting point

`scoutbot-baseline/` is Week 8 Day 3's reference solution: Week 7's loop untouched, Monday's explicit
state, Tuesday's conditional edge and checkpointer, Wednesday's streamed draft and real pause.
**Everyone extends this same baseline today, in place.** Four things to know:

- **Nothing to install.** `RetryPolicy` ships inside `langgraph`, and everything else you need is in
  the standard library.
- **The ticket data is already updated for you.** Every ticket in `sample_tickets.json` has a
  `refund_amount`, and `mock_customers.json` has a customer with four refunds in ninety days whose
  ticket is for twelve euros fifty. No code reads either yet.
- **Some existing tests will start failing, and that is expected.** Several assert on
  `route_after_triage` and on the exact pause payload, and today changes both. Updating them is part
  of the task, not a mistake you made.
- **`loop.py` still doesn't change**, and `uv run python main.py` should still work when you're done.

## Your task

Working in pairs, on a new branch, extending `scoutbot-baseline/` in place:

### Part 1 — Decide who signs (approval policy)

1. **Wire the amount through.** Add `refund_amount` to `TicketState` and to `initial_state()`, and
   pass each ticket's amount in from `run_graph.py`. Small step, and worth noticing what it is: an
   input the graph is *given*, not something a node works out. No node should ever set this field.
2. **Write the policy as a pure function**, in its own module. Something like:

   ```python
   def decide_approval(amount, plan, past_refunds_90d, priority) -> ...:
       """Whether a human is needed, AND which approver is required."""
   ```

   Rules are yours to choose, but make them defensible: at least one threshold on the amount, at
   least two different approvers, and at least one rule that is **not** about the amount — the
   twelve-euro ticket from the customer with four refunds should still reach a person. Keep the whole
   module free of model calls, graph imports and I/O. It should be importable on its own.
3. **Return the reason too, not just the verdict.** The approver is about to be interrupted; tell them
   which rule pulled them in. A decision nobody can question is a decision nobody can correct.
4. **Test the table before you wire it in.** This is the payoff for keeping it pure: no API key, no
   graph, no mock, and you can cover every branch and both sides of every threshold in a few seconds.
   Do this step *before* step 5 — it is much easier to debug a function than a graph.
5. **Route on the decision.** Have a node apply the policy and write the result into state, then have
   the router read that field rather than computing anything itself. Ask yourselves why the decision
   goes into state at all, rather than being made inside the router: what can you do a week later with
   one arrangement that you cannot with the other?
6. **Name the approver in the pause payload**, then **check the answer you get back.** Whatever you
   pass to `Command(resume=...)` arrives in the node exactly as given — LangGraph validates nothing —
   so a support lead's approval of a billing manager's decision arrives looking perfectly valid.
   Decide what your node does about it, and be able to justify the choice. Note that a person's *name*
   and their *role* are different things, and only one of them is any use to a policy.

### Part 2 — Send it once (idempotency)

7. **Make the graph actually send something.** Add a node whose job is to send the reply — a `print`
   counts as an email — and have **both** branches lead to it. Ask why one shared node beats sending
   from each branch before you write it.
8. **Reproduce the double send.** Move that send temporarily into `escalate_node`, *above* the
   `interrupt()` call, then run and resume. Count the emails. One approval, two emails. Keep it broken
   for a moment and look at it.
9. **Try the obvious fix, and watch it fail.** Guard the send with the run's own state: `if
   state["sent"]: return` and `return {"sent": True}` at the end of the node. Run it again and count
   the emails again. Then work out *why* it did not help. Then look at the final state and notice what
   it says about `sent`, which is the genuinely dangerous part. Write down, in a sentence, what is
   wrong with this approach — that sentence is most of what today is about.
10. **Put the record somewhere it survives.** Undo step 8's move, so the send is back in its own node
    below the pause. Now give the send a durable record of what it has already done: a table in the
    same SQLite file the checkpointer uses is plenty. Before sending, ask the record. After sending,
    write to it — immediately, not at the end of the function, and be ready to say why.
11. **Choose the key carefully.** The record needs a key, and the key is the whole design. What makes
    two attempts "the same action"? Try `uuid4()` in the node once, so you can see what a wrong key
    does: it will look like it works and dedupe nothing.
12. **Now add a retry, and be the failure.** Register your send node with
    `retry_policy=RetryPolicy(max_attempts=3)` (from `langgraph.types`) and make the send fail twice
    *after* the email has gone out — the gateway took the message and then the connection dropped, so
    your code never learned it had succeeded. Run it. Three attempts, one email. Then ask what would
    have happened if you had made it fail *before* the send instead, and why that version of the demo
    would have taught you nothing.
13. **Write tests for both guarantees**, and make one of them a counterfactual: a version with no
    durable record that sends three, next to the version that sends one. A guarantee is only
    meaningful beside what happens without it. Then fix the existing tests your changes broke.
14. **Same habit as every day**: commit on your branch, open a PR back to main.

## Expected outcome (minimum requirements)

- [ ] **`refund_amount` flows from the ticket data into state**, and no node ever sets it
- [ ] **An approval policy as a pure module**: no model, no graph, no I/O, importable on its own
- [ ] **At least two approvers and at least one rule that is not about the amount**
- [ ] **Every decision carries a reason** that a human reading the pause can act on
- [ ] **Tests for the policy table**, covering both sides of at least one threshold, running with no
  API key
- [ ] **The router reads the decision** rather than making it
- [ ] **The pause names the required approver**, and an approval from the wrong role is refused
- [ ] **One node sends the reply, and both branches lead to it**
- [ ] **Evidence of the double send**, and a written sentence on why guarding it with the run's own
  state does not work
- [ ] **A durable record that makes the send happen once**, keyed on something stable
- [ ] **Three send attempts under a `RetryPolicy`, and exactly one email**, with the failure occurring
  *after* the send
- [ ] At least one test for the once-only guarantee, and one counterfactual showing the duplicate
- [ ] The existing tests your change broke are updated, not deleted or skipped
- [ ] `loop.py` unchanged, and `uv run python main.py` still works
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Two approvers on one ticket.** Make a very large refund require *both* a support lead and a
  billing manager, with two `interrupt()` calls in the same node. Predict what happens to the first
  answer when the second pause resumes, before you run it. Then check: how many times did the code
  above the first `interrupt()` run, versus the code between the two?
- **Ask again instead of giving up.** Your node refuses an approval from the wrong role, but the run
  then finishes, refused. Make it pause again instead, until somebody authorised answers. Then decide
  whether you actually want that: what does an unbounded loop of pauses do to a ticket nobody senior
  ever looks at, and where would you put the limit?
- **Find out what `CachePolicy` actually does.** Students reach for it here every year. Put
  `cache_policy=CachePolicy(ttl=60)` on your send node, invoke the same ticket twice, and count the
  emails. Then read `compile()`'s signature and try again. Two separate lessons in one experiment, and
  neither of them is idempotency.
- **Find the window.** There is a moment in your send node where a crash still produces a duplicate,
  no matter how good your key is. Find it, then work out what it would take to close it, and whether
  you could close it for an email API at all.
- **Make the policy readable by Dana.** Print your approval table as a plain-language summary — one
  line per rule, no code — and ask whether the person who owns refunds could check it for mistakes.
- **Put the ledger in `get_state_history()`'s company.** Look at a thread's history alongside your
  ledger rows, and work out which questions each one can answer that the other cannot.

## If you're running out of time

Protect Part 2, and specifically steps 8-10 and 12. Feeling the double send, watching the state guard
fail, and then getting to one email under a retry is what the day is assessed on. Part 1 is the first
to trim: a policy with two rules and one approver still lets you do all of Part 2, so cut the table
down rather than cutting the second half. Step 11's `uuid4()` experiment and step 13's counterfactual
test are next. Flag whatever you skipped rather than quietly leaving it out. (Coaches: see the
coaches' page "Contingency plans" for exactly what to prioritise.)
