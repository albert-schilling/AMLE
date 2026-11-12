# User story 3: the status check is flaky

Related story: [user_story_3.md](user_story_3.md)

## Problem

For ticket T-2001 the agent sometimes does not call `web_fetch` at all. It answers
with the final JSON (`billing`, `high`) at step 1, without checking the Mollie status.
Its own thinking said it would check first.

## Observed (real API, `claude-haiku-4-5`, T-2001, all Mollie components up)

| Prompt | Runs with fetch |
| --- | --- |
| "check the status ... before deciding" | 3 of 7 |
| "you must call web_fetch ... before you answer or escalate" | 2 of 4 |

When the fetch happens, it works: `web_fetch ok`, guardrails hold (`max_uses`,
`allowed_domains`). The skipping also happens for `lookup_customer`, so it is not caused
by the web fetch tool.

## Likely cause

`output_format` (structured output) lets the model end the turn with the JSON at any
time. Tools are optional (`tool_choice: auto`), and a small model sometimes takes the
shortcut. A stronger prompt did not fix it.

## Suggested fixes

1. **Stronger model.** `claude-haiku-5-5` (supported by web fetch). It needs adaptive
   thinking instead of `THINKING_BUDGET` (see [TODO.md](../TODO.md)). **Tested:** 10 runs
   of T-2001 with `MODEL=claude-haiku-5-5` and `THINKING_BUDGET=0`: it called `web_fetch`
   in 10 of 10 runs (and `lookup_customer` first every time), versus 3 of 7 for
   `claude-haiku-4-5`. Small sample, all-components-up case only. The default model in
   `config.py` is still `claude-haiku-4-5`.
2. **Code gate.** For billing tickets, fetch the status in code first and give the result
   to the model as context. Reliable, but the agent no longer decides.
3. **Retry on skip.** If a billing ticket ends without a `web_fetch` call, run it once
   more or escalate as "status unverified". Needs a check on the response blocks.
4. **Force the tool.** `tool_choice` set to the tool for the first turn. Works only for
   client tools in the tool runner, and it also clashes with `disable_parallel_tool_use`.
5. **Measure first.** Run T-2001 20 times per model and prompt, then decide.
