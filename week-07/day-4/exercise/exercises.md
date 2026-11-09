# W7D4 Exercise — Wire In Both Tools

## Scenario

Dana has two new asks for ScoutBot: check a vendor's live status page before assuming a
duplicate charge is Anchorpoint's fault, and pull a real number out of a messy app log
instead of guessing at one. Both need a tool that reaches outside ScoutBot's own process —
today, you wire in Anthropic's two server tools that do exactly that.

## Starting point

`scoutbot-baseline/` is Day 2's reference solution — the bounded ReAct loop with
`look_up_customer` and `escalate_to_human`, unchanged. **Everyone starts from this same
baseline today**, regardless of how far you got on your own Day 2 code. Also inside:

- `sample_app.log` — a small sample log to parse (no need to invent your own).
- `sample_tickets.json` — Day 2's 3 tickets, plus two new ones (`T-2001`, `T-2002`) written
  for today's two tools.

## Your task

Working in pairs, on a new branch, starting from `scoutbot-baseline/`:

1. **Add the `web_fetch` tool** with `allowed_domains` set to one real status-page domain,
   plus a system-prompt line treating fetched content as data only, never as instructions.
2. **Add the `code_execution` tool**, and have ScoutBot use it to parse the provided sample
   log file.
3. **Update the loop** to handle server tool results alongside the loop's existing client
   tool results.
4. **Prove it**: run one ticket that needs the status check (`T-2001`), and one that needs
   the log parse (`T-2002`), end to end.
5. **Same habit as every day**: commit on your branch, open a PR back to main.

## Expected outcome (minimum requirements)

- [ ] `web_fetch` is wired in with `allowed_domains` set, and a real fetch happens on `T-2001`
- [ ] `code_execution` is wired in, with one real run against `sample_app.log` on `T-2002`
- [ ] The loop update handles both client and server tool results, not just client ones
- [ ] One written line (a sentence or two is enough) on what you'd still restrict further —
  `allowed_domains` narrows *where* ScoutBot can fetch from, but not what it does once it's
  there
- [ ] Running `T-2001` and `T-2002` end to end prints the full trace for each, including the
  server tool step
- [ ] At least one test covering the loop's new server-tool-result handling (mocking the
  model, same pattern as every earlier day)
- [ ] Work is on a branch with an open pull request

## If you finish early

- Add a `max_content_tokens` limit to `web_fetch`, and explain out loud (to your pair or a
  coach) why a limit matters even for a page you trust.
- Detect a `code_execution` run that returned a non-zero `return_code` and have ScoutBot say
  so explicitly in its final answer, instead of silently treating any output as a good one.

## If you're running out of time

It's fine to stop once one of the two server tools actually fires end to end, even without
the second one wired in — flag which one is missing rather than hiding it. The written
guardrail line is quick; don't skip it under time pressure just because it isn't code.
(Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
