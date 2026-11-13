# Architecture

## 1. `classify` has too many jobs — done

Split into `build_runner`, `run_loop` (returns final message and `LoopStats`),
`to_result` (cap and escalation logic, unit-tested alone) and `summarize`.
`final_record(ticket_id, result, stats)` replaced the seven positional arguments.

## 2. Hidden global settings

`get_settings()` is called inside `prompts`, `tools`, `customers` and `classifier`.
Every layer reads the environment on its own. This is why tests need the autouse
cache-clearing fixture.

Fix: read settings once in `cli.main` and `evals.main`, then pass `settings` (or only
the needed values) down: `create_prompt(ticket, status_url, payments_url)`,
`make_fetch_tool(settings)`, `classify(ticket, client, approve, settings, ...)`.

## 3. API client code lives in the classifier

`create_client` and `upload_log` are in `classifier.py`, and `cli.py` imports them from
there. They are API setup, not classification.

Fix: move them to `client.py`.

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
