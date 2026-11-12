# Behavior evals

Unit tests cannot show that the model follows the prompt and uses its tools. The eval runs
real tickets against the API several times and prints how often each check passed.

```
make eval                                            # 5 runs per ticket
uv run python -m ticket_classifier.evals --runs 10
```

- Code: [evals.py](../src/ticket_classifier/evals.py). Checks read the trace (`Action:` / `Observation:`).
- Calls the real API, so it costs money. Results vary between runs: read them as pass rates.
- Uses the model and settings from the environment (`MODEL`, `FETCH_BACKEND`, `THINKING_BUDGET`).

| Ticket | Checks |
| --- | --- |
| T-2001 | fetched the Mollie status page |
| T-2002 | ran code; code printed 5; at most 3 code calls |
| T-2004 | fetched payments; tool found the duplicate |
| T-2005 | fetched payments; tool found no duplicate |

## Model comparison (5 runs per ticket)

| Check | `claude-haiku-4-5` | `claude-haiku-5-5` |
| --- | --- | --- |
| T-2001 fetched status | 5/5 | 5/5 |
| T-2002 ran code | 1/5 | 5/5 |
| T-2002 code printed 5 | 1/5 | 3/5 |
| T-2002 at most 3 code calls | 4/5 | 5/5 |
| T-2004 fetched payments / found duplicate | 0/5 / 0/5 | 5/5 / 5/5 |
| T-2005 fetched payments / found none | 1/5 / 1/5 | 5/5 / 5/5 |

Settings differ: Haiku 4.5 ran with `FETCH_BACKEND=server` and thinking on (default); Haiku 5.5 ran with
`FETCH_BACKEND=local` and `THINKING_BUDGET=0`.

**Reading:** Haiku 4.5 often skips its tools and answers with the structured JSON right away
(T-2001 passes because the prompt demands the status fetch). Haiku 5.5 used its tools in all runs.
The default model is still Haiku 4.5. Switching needs adaptive thinking instead of `THINKING_BUDGET`
(see [TODO.md](TODO.md)). Related: [user_story_3_flaky_fetch.md](user-stories/user_story_3_flaky_fetch.md).
