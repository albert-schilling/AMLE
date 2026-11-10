# TODO

From the critical review of the agent loop.

## Bugs / correctness

1. **Cap path drops an approved escalation.** The runner executes the last pending tool
   call even after the final allowed turn. If that is `escalate_to_human`, the human is
   prompted and may approve, but `classify` sees `stop_reason == "tool_use"`, reports
   "Iteration cap reached" and loses the approved reason.
   Fix: check `escalation.reason` first (the approved reason wins) and skip the prompt
   on the final turn.
2. **Auth errors repeat for every ticket.** `classify_all` catches `APIError` per ticket
   and continues, so a bad API key or rate limit fails each ticket slowly. Abort the
   batch on `AuthenticationError`.

## Verification

3. **Never run against the real SDK.** All tests use `FakeRunner`, which encodes our
   reading of the runner (iterate, then `until_done()`; `generate_tool_call_response()`
   cached so tools run once). Run `make run` on the 3 sample tickets and check the trace;
   consider one test that fakes the HTTP layer instead of the runner.

## Design

4. **`TriageResult` / `ClassifiedTicket` allow impossible states** (`escalated=False` with
   a reason; no classification and no escalation). Add a validator or a tagged union.
   `category: null` in the output file must be handled by consumers.
5. **`classify` has too many jobs** (build request, drive loop, log, interpret outcome).
   Split "run loop" from "turn messages into a result" so the cap logic is testable alone.

## Open decisions / smaller points

- Approval does not end the loop; the model keeps going after "a human will take over".
- `input()` in `console_approval` blocks with no timeout.
- README says "steps" for `MAX_ITERATIONS`; the SDK counts model replies (same here).
