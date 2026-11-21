# Ticket Classifier

Classifies support tickets into a category (`billing`, `technical`, `account`, `other`)
and a priority (`low`, `medium`, `high`) with Claude, as a LangGraph workflow:

```
START → get_customer → triage → high priority? → human_review → END
                                         else → mark_handled → END
```

- `get_customer` reads the customer from `CUSTOMERS_PATH` (if the ticket has an id).
- `triage` makes one structured-output call to Claude. No classification (refusal,
  `max_tokens`) fails the ticket; the next run retries it.
- `human_review` pauses the run until a person answers (see below).
- Each ticket is its own thread; runs are saved in SQLite and survive a crash or exit.
- Every workflow event (node update, pause, finish) is appended as one JSON line to
  `TRACE_FILE` (default `output/trace.jsonl`), with `ticket_id`, `node`, `event` and
  `data`. The graph is saved as mermaid to `GRAPH_PATH`.

## Setup

```sh
make setup                      # uv sync
cp .env.example .env            # then set ANTHROPIC_API_KEY
```

## Usage

```sh
make run                        # uses TICKETS_PATH
uv run ticket-classifier run path/to/tickets.json
uv run python -m ticket_classifier run   # same program, without the console script
```

Calls the Anthropic API and may incur charges.

### Human review of high-priority tickets

A high-priority ticket pauses in `human_review` (`interrupt()`) and waits for a
person. The run is saved in `CHECKPOINT_PATH` (SQLite, default `output/checkpoints.db`),
so the process can exit. The run log shows what the reviewer needs (ticket, customer,
classification) and the command to answer:

```sh
uv run ticket-classifier resume T-3 --approve --note "Dana takes it"
uv run ticket-classifier resume T-3 --decline --note "Bot can answer"
make approve TICKET=T-3 NOTE="Dana takes it"   # same, via make
make decline TICKET=T-3 NOTE="Bot can answer"
```

A resume needs only the ticket id (the saved run has the ticket), finishes only that
ticket, makes no model call and adds its result to
`results.json` without removing the others. `--approve` gives `escalated: true` with
the note as reason, `--decline` gives `escalated: false`. Paused tickets are not in
`results.json` until they are answered; a normal run leaves them paused.

A second `run` does not classify finished tickets again: it reuses their saved result
(no model call) and continues crashed runs where they stopped. To classify everything
again, run `make reset` (deletes saved runs, trace and results; paused tickets are lost).

While a run works, nodes emit progress events (e.g. `calling model`), logged as
`[custom]` lines. `LOG_LEVEL=DEBUG` also logs every state update.

Exit code: `0` every ticket got a result or is paused for a human, `1` some tickets
failed (the rest are still saved), `2` input could not be loaded or the ticket to
resume has no paused run.

`run` without `ANTHROPIC_API_KEY` stops with exit code `2`; `resume` needs no key. An
invalid setting (e.g. `LOG_LEVEL=LOUD`) stops at startup with a traceback.

**Input** (`fixtures/tickets.json`): list of `{"id", "text", "customer_id"?}`.
Customers are read from `CUSTOMERS_PATH` (JSON object keyed by customer id).

**Output** (`output/results.json`, git-ignored):

```json
[{"ticket_id": "T-1", "customer_id": "1001", "category": "billing",
  "priority": "high", "escalated": false, "escalation_reason": null}]
```

## Configuration

Environment variables or `.env`, see [.env.example](.env.example):
`ANTHROPIC_API_KEY` (required for `run`), `MODEL`, `MAX_TOKENS`, `LOG_LEVEL`, `LOG_FILE`,
`TRACE_FILE`, `TICKETS_PATH`, `CUSTOMERS_PATH`, `RESULTS_PATH`,
`CHECKPOINT_PATH`, `GRAPH_PATH`.

OpenTelemetry (off by default): `OTEL_ENABLED`, `OTEL_SERVICE_NAME`,
`OTEL_EXPORTER_OTLP_ENDPOINT` (empty prints to the console),
`OTEL_RESOURCE_ATTRIBUTES`. The local stack: [monitoring/README.md](monitoring/README.md).

## Layout

| Module | Role |
| --- | --- |
| `cli.py` | entry point: dispatch to a command, exit codes |
| `args.py` | subcommands `run` and `resume`, parsed into `RunArgs` / `ResumeArgs` |
| `commands.py` | what the subcommands do: open checkpointer, build graph, run, save results |
| `checkpoint.py` | SQLite checkpointer that loads only known state types |
| `runner.py` | run each ticket in its own thread (streamed), resume paused or crashed runs, collect failures |
| `graph.py` | build the workflow, write the mermaid diagram |
| `nodes/` | one file per node, the router, the node names |
| `prompts.py`, `client.py` | system prompt and user message, Anthropic client |
| `customers.py` | customer data access (swap for a DB later) |
| `storage.py` | read tickets, write or merge results |
| `trace.py`, `logging_config.py` | JSON lines trace, logger setup |
| `telemetry.py` | OpenTelemetry: settings to the SDK, start TraceVerde, send our logs |
| `models/` | data only: `domain.py` (input), `state.py` (graph state), `results.py` (output rows) |
| `config.py` | settings |

## Development

```sh
make test      # pytest, no API calls
make reset     # delete saved runs, trace and results
make lint
make format
```

Code conventions: [docs/conventions.md](docs/conventions.md). Instructions for AI
agents: [AGENTS.md](AGENTS.md).
