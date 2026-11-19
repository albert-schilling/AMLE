# TODO

Open points for the LangGraph workflow. Finished items move to the bottom.

## Features

- **Team assignment** is missing (user story 1 asks for team and urgency).
- **Draft reply** for the customer (user story 2) is not implemented.
- **Review over the CLI only.** `resume` is fine for one person; real use needs a queue
  or UI that lists paused tickets with their `EscalationRequest`.
- **One question per pause.** A second `interrupt()` in `human_review` would need the
  resume code to answer several questions in order.

## Quality

- **No evals for the graph.** Unit tests mock the model; nothing measures how well
  real triage classifies (e.g. a labelled ticket set, pass rates per model).
- **Prompt:** no examples of the expected output; no test against real prompt
  injection attempts (the ticket text is only tagged and marked untrusted).
- **No maximum ticket length.** A very long ticket costs tokens or hits `max_tokens`.
- **Token usage is not tracked.** `output.usage` could go into the trace.

## Stand-ins

- **Customers from a JSON file** (`fixtures/customers.json`): replace the body of
  `get_customer` with a database or API call.
- **One SQLite file for saved runs**: fine for one process; parallel runs need a
  server-backed checkpointer (e.g. Postgres).

## Done

- Week 7 agent loop removed; the app is the LangGraph workflow only.
- Pause for a human with `interrupt()`, resume from a second process.
- A finished ticket is not run again; a crashed run continues where it stopped.
- No classification (refusal, `max_tokens`) fails the ticket instead of the batch.
