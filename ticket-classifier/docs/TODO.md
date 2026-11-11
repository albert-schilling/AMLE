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

- **One tool call per turn** (`disable_parallel_tool_use`) was added but not yet checked
  in a real run: expect lookup first, then escalation, in separate steps.
- **`THINKING_BUDGET` only works for models with manual extended thinking** (e.g. Haiku
  4.5). Claude 4.7 and later (e.g. `claude-haiku-5-5`) reject `type: "enabled"` with a
  400; they need `{"type": "adaptive"}` plus an effort level. If `MODEL` is switched,
  thinking must change too. Consider a startup check or warning, or a setting that
  selects the mode.
- **No temperature / sampling control:** API version `2026-10-21` (the SDK default)
  rejects `temperature`, `top_p` and `top_k` on every model, and older versions forbid
  them with thinking on. Run-to-run variation can only be reduced by prompt, thinking, or
  voting (run twice, escalate on disagreement).
- Approval does not end the loop; the model keeps going after "a human will take over" and
  makes one more API call to classify.
- `input()` in `console_approval` blocks with no timeout.
- README says "steps" for `MAX_ITERATIONS`; the SDK counts model replies (same here).
- Thinking is on by default (`THINKING_BUDGET=2000`): extra tokens per ticket.
- Exercise bonus items not done: a third tool (e.g. `draft_reply`), stuck-loop detection
  (same tool and arguments twice in a row).

## Done

- Thinking only at step 1: explained, not a bug. Haiku 4.5 has no interleaved thinking
  (official docs). Revisit only when switching models (see above).
- Multi-line thinking in the log file: the file handler writes newlines as a literal
  `\n`, so one record is one line (greppable); the console keeps real newlines.
- Run against the real SDK: loop, tool calls, approval, rejection (`n`) and thinking all
  worked in real runs; trace order fixed (Action logged before tools run).
- Parallel tool use (escalating before the customer lookup) fixed with
  `disable_parallel_tool_use`; see the open point above to verify it in a real run.
- Rejection path verified on the real API (previously mock-only).
- PR #2 (agent loop, escalation gate, trace logging, thinking) merged.
