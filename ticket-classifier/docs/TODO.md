# TODO

Open points from the critical review of the agent loop. Finished items are listed at the
bottom so the history stays clear.

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

## Design

3. **`TriageResult` / `ClassifiedTicket` allow impossible states** (`escalated=False` with
   a reason; no classification and no escalation). Add a validator or a tagged union.
   `category: null` in the output file must be handled by consumers.
4. **`classify` has too many jobs** (build request, thinking options, drive loop, log,
   interpret outcome). Split "run loop" from "turn messages into a result" so the cap
   logic is testable alone.

## Open decisions / smaller points

- **Thinking only appears at step 1**, not after tool results. Check whether Haiku 4.5
  needs the interleaved-thinking beta header, or whether nothing is thought there.
- **One tool call per turn** (`disable_parallel_tool_use`) was added but not yet checked
  in a real run: expect lookup first, then escalation, in separate steps.
- Approval does not end the loop; the model keeps going after "a human will take over" and
  makes one more API call to classify.
- `input()` in `console_approval` blocks with no timeout.
- README says "steps" for `MAX_ITERATIONS`; the SDK counts model replies (same here).
- Thinking is on by default (`THINKING_BUDGET=2000`): extra tokens per ticket.
- Exercise bonus items not done: a third tool (e.g. `draft_reply`), stuck-loop detection
  (same tool and arguments twice in a row).

## Done

- Multi-line thinking in the log file: the file handler writes newlines as a literal
  `\n`, so one record is one line (greppable); the console keeps real newlines.
- Run against the real SDK: loop, tool calls, approval, rejection (`n`) and thinking all
  worked in real runs; trace order fixed (Action logged before tools run).
- Parallel tool use (escalating before the customer lookup) fixed with
  `disable_parallel_tool_use`; see the open point above to verify it in a real run.
- Rejection path verified on the real API (previously mock-only).
- PR #2 (agent loop, escalation gate, trace logging, thinking) merged.
