# Architecture

## 1. `classify` has too many jobs

Already in TODO (design 4). [classifier.py](../../src/ticket_classifier/classifier.py)
builds the request, drives the loop, counts tokens and time, writes traces and decides
the outcome.

Concrete proposal:

- `run_loop(...) -> (final_message, LoopStats)` drives the runner and writes step records.
- `LoopStats` dataclass: `steps`, `input_tokens`, `output_tokens`, `container_ms`.
- `to_result(final_message, escalation, settings) -> Resolved | Escalated` holds the
  cap and escalation logic and is testable alone.
- `final_record(ticket_id, result, stats)` instead of seven positional arguments. Today
  it is called twice with `True, None, steps, ...`
  ([classifier.py:134-145](../../src/ticket_classifier/classifier.py#L134-L145)), which
  is easy to get wrong.

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
