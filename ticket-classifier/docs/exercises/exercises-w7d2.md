# W7D2 Exercise — Give ScoutBot a Loop

## Scenario

Priya rebuilt ScoutBot's triage core yesterday. Dana is thrilled — and now wants ScoutBot to
actually help resolve tickets: look up the customer, decide whether to escalate, not just label
them. That needs more than one tool call. Today, you build the loop.

## Starting point

`scoutbot-baseline/` is yesterday's reference solution — a working, tested `triage()`
function, in a real repo. **Everyone starts from this same baseline today**, regardless of how
far you got on your own Day 1 code. Also inside:

- `mock_customers.json` — fake account data for the customer-lookup tool you'll add (no need
  to invent your own).
- `sample_tickets.json` — the same 3 tickets as yesterday, now each with a `customer_id`.

## Your task

Working in pairs, on a new branch, starting from `scoutbot-baseline/`:

1. **Add two tools**
    - `look_up_customer(customer_id)` — reads `mock_customers.json`, read-only.
    - `escalate_to_human(reason)` — must not take effect without a human approval step (a
      simple y/n prompt is enough).
2. **Implement the loop**
    - Send the ticket to the model along with all three tools (yesterday's `triage_ticket`
      plus your two new ones).
    - Let it reason, call a tool, observe the result, and decide again — repeating until it
      gives a final answer with no tool call.
    - Add a **hard iteration cap** (start with 6 steps). If the cap is hit, treat it as an
      automatic escalation — don't just crash or loop forever.
3. **Gate the risky action**
    - `escalate_to_human` must not "count" as executed until a human approves it. Rejecting it
      should feed back into the loop as a normal observation, not end the run.
4. **Prove it**
    - Run your loop on all 3 sample tickets and print the full reasoning trace — every
      Thought, Action, and Observation — plus the final answer for each.
5. **Same habit as yesterday**
    - Commit on your branch, open a PR back to main.

## Expected outcome (minimum requirements)

- [x] The loop reasons, acts, observes, and repeats — not a single call
- [x] A hard iteration cap is in place (the loop cannot run forever)
- [x] At least 2 new tools exist beyond yesterday's `triage_ticket`
- [x] `escalate_to_human` requires a human approval step before it "counts" as executed
- [x] Running your code on all 3 sample tickets prints the full trace for each
- [x] At least one test (mocking the model, same pattern as yesterday)
- [x] Work is on a branch with an open pull request

## If you finish early

- Add a third tool (e.g. `draft_reply`) and decide, using yesterday's autonomy framework,
  whether it needs a gate too.
- Detect a stuck loop (the same tool called with the same arguments twice in a row) and stop
  early with a clear message, instead of waiting for the step cap.

## If you're running out of time

It's fine to stop once your loop calls at least one new tool and produces a final answer, even
without the approval gate — flag what's missing rather than hiding it. (Coaches: see the
coaches' page "Contingency plans" for exactly what to prioritise.)
