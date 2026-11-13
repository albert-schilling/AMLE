# Temporary and experimental implementations

Code that exists to try something out (user story exercises, fake data, stand-ins).
None of it is wrong. It should get a decision before real use: keep, replace or remove.

| # | What | Where | Why it exists | Before real use |
| --- | --- | --- | --- | --- |
| 1 | Local fetch backend (`FETCH_BACKEND=local`) | `safe_fetch.py`, `make_local_fetch_tool`, `make_fetch_tool`, `httpx2` dependency | User story 3.3: compare our own sandboxed fetch with Anthropic's server `web_fetch`. Default is `server`. | Keep one backend. Local has a known DNS rebinding gap and got `HTTP 403` from the Mollie status page. |
| 2 | Fake payments data | `docs/payments.json` on GitHub Pages, `PAYMENTS_DOMAIN`, `PAYMENTS_URL`, `Payment` model | User story 3: fake data to test duplicate charge detection. | Replace with the real payment provider API; the model should not carry payment rows into a tool call. |
| 3 | Payment rows passed through the model | `find_duplicate_charges(client_id, payments)` | The model fetches the JSON and hands the rows to the tool. Simple for the exercise. | Let the tool fetch the data itself; saves tokens and the model cannot alter rows. |
| 4 | Customers from a JSON file | `customers.py`, `fixtures/customers.json` | Stand-in data source ("swap for a DB later"). | Replace the body of `get_customer` with a database or API call. |
| 5 | Console approval with `input()` | `approval.py` | Simplest human gate for interactive runs. No timeout; without a terminal it rejects. | Replace with a real review queue or ticket system hand-off. |
| 6 | Sample log upload for code execution | `LOG_PATH` (`fixtures/sample_app.log`), `upload_log`, `LOG_ANALYSIS` prompt, `CODE_EXECUTION_TOOL` | User story 4: extract a number from a log file for ticket T-2002. One fixed file is attached to every ticket. | Attach only the logs a ticket needs; decide on privacy (the story says "ignore privacy concerns for now"). |
| 7 | Manual extended thinking (`THINKING_BUDGET`) | `build_runner` in `classifier.py` | Exercise: make the model's reasoning visible. Works only on models with manual thinking (e.g. Haiku 4.5). | Switch to adaptive thinking when changing to a Claude 4.7+ model (see TODO). |
| 8 | Hard-coded Mollie status check | `STATUS_DOMAIN`, `STATUS_URL`, `STATUS_CHECK` prompt | User story 3: check one provider's status page. | Fine if Mollie stays the provider; otherwise make it configurable per provider. |
| 9 | `container_ms_estimate` | `trace.py` | The API reports no container time, so the whole step time is used as an upper bound. | Replace with real container time if the API adds it. |
| 10 | Evals that parse log text | `evals.py` | Quick behavior checks on the real API. | Check the JSONL step records instead (see [architecture.md](architecture.md) item 5). |

## Not implemented, plan only

- `web_search` (user story 3.1): described in
  [../user-stories/user_story_3_1_web_search.md](../user-stories/user_story_3_1_web_search.md),
  no code yet.
