# Architecture

## 1. `classify` has too many jobs — done

Split into `build_runner`, `run_loop` (returns final message and `LoopStats`),
`to_result` (cap and escalation logic, unit-tested alone) and `summarize`.
`final_record(ticket_id, result, stats)` replaced the seven positional arguments.

## 2. Settings singleton — kept by choice

`get_settings()` (cached with `@cache`) is the config singleton: read once, used
from anywhere. Passing `settings` down every layer was considered and rejected: it is
prop drilling for no real gain. `WEB_FETCH_TOOL` reads it at import on purpose.

Costs, accepted:

- tests clear the cache in the autouse fixture `_isolated_settings`;
- `conftest.py` sets `ANTHROPIC_API_KEY` before any package import.

Pure helpers may still take plain values (e.g. a URL) when that reads naturally.

## 3. API client code lives in the classifier — done

`create_client` and `upload_log` moved to `client.py`; their test to `tests/test_client.py`.

## 4. Two parallel union pairs

`Resolved / Escalated` (domain result) and `ResolvedTicket / EscalatedTicket` (output
row) hold almost the same data, and `batch.to_classified_ticket` maps one to the other.

Options: keep both if the output schema must stay independent of the domain model;
otherwise one output model built from `TriageResult` with `ticket_id` and
`customer_id` added, and `to_classified_ticket` goes away.

## 5. Evals parse log text

[evals.py](../../src/ticket_classifier/evals.py) checks strings like `"Action: tool("`
from the trace logger. Rewording a log line breaks the evals silently.

Fix: check the structured step records (`tool_calls`, `observation`) instead, e.g. by
collecting the dicts from `step_record` rather than log messages.
