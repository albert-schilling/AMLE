# Ticket Classifier

Classifies support tickets into a category (`billing`, `technical`, `account`, `other`)
and a priority (`low`, `medium`, `high`) with Claude, as a LangGraph workflow:

```
START → node_get_customer → node_triage → high priority? → node_wait_for_human → END
                                                   else → node_mark_handled  → END
```

- `node_get_customer` reads the customer from `CUSTOMERS_PATH` (if the ticket has an id).
- `node_triage` makes one structured-output call to Claude.
- `node_wait_for_human` pauses the run until a person answers (see below).
- Each ticket is its own thread; runs are saved in SQLite and survive a crash or exit.
- Every node update is appended as one JSON line to `TRACE_FILE`
  (default `output/trace.jsonl`). The graph is saved as mermaid to `GRAPH_PATH`.

## Setup

```sh
make setup                      # uv sync
cp .env.example .env            # then set ANTHROPIC_API_KEY
```

## Usage

```sh
make run                        # uses TICKETS_PATH
uv run ticket-classifier path/to/tickets.json
uv run python -m ticket_classifier   # same program, without the console script
```

Calls the Anthropic API and may incur charges.

### Human review of high-priority tickets

A high-priority ticket pauses in `node_wait_for_human` (`interrupt()`) and waits for a
person. The run is saved in `CHECKPOINT_PATH` (SQLite, default `output/checkpoints.db`),
so the process can exit. The run log shows what the reviewer needs (ticket, customer,
classification) and the command to answer:

```sh
uv run ticket-classifier --resume T-3 --approve --note "Dana takes it"
uv run ticket-classifier --resume T-3 --decline --note "Bot can answer"
make approve TICKET=T-3 NOTE="Dana takes it"   # same, via make
make decline TICKET=T-3 NOTE="Bot can answer"
```

A resume finishes only that ticket, makes no model call and adds its result to
`results.json` without removing the others. `--approve` gives `escalated: true` with
the note as reason, `--decline` gives `escalated: false`. Paused tickets are not in
`results.json` until they are answered; a normal run leaves them paused.

While a run works, nodes emit progress events (e.g. `calling model`), logged as
`[custom]` lines. `LOG_LEVEL=DEBUG` also logs every state update.

Exit code: `0` every ticket got a result or is paused for a human, `1` some tickets
failed (the rest are still saved), `2` input could not be loaded.

A missing or invalid setting (e.g. no `ANTHROPIC_API_KEY`) is not handled: the program
stops at startup with a traceback and exit code `1`.

**Input** (`fixtures/tickets.json`): list of `{"id", "text", "customer_id"?}`.
Customers are read from `CUSTOMERS_PATH` (JSON object keyed by customer id).

**Output** (`output/results.json`, git-ignored):

```json
[{"ticket_id": "T-1", "customer_id": "1001", "category": "billing",
  "priority": "high", "escalated": false, "escalation_reason": null}]
```

## Configuration

Environment variables or `.env`, see [.env.example](.env.example):
`ANTHROPIC_API_KEY` (required), `MODEL`, `MAX_TOKENS`, `LOG_LEVEL`, `LOG_FILE`,
`TRACE_FILE`, `TICKETS_PATH`, `CUSTOMERS_PATH`, `RESULTS_PATH`,
`CHECKPOINT_PATH`, `GRAPH_PATH`.

## Layout

| Module | Role |
| --- | --- |
| `cli.py` | argument parsing, checkpointer setup, exit codes |
| `batch.py` | run each ticket through the graph, resume paused or crashed runs, collect failures |
| `graph.py` | build the workflow, write the mermaid diagram |
| `nodes.py`, `triage_node.py` | the nodes and the router |
| `prompts.py`, `client.py` | system prompt, Anthropic client |
| `customers.py` | customer data access (swap for a DB later) |
| `storage.py` | read tickets, write or merge results |
| `trace_graph.py`, `logging_config.py` | JSON lines trace, logger setup |
| `models.py`, `config.py` | pydantic models, state and settings |

## Development

```sh
make test      # pytest, no API calls
make lint
make format
```

Code conventions: [docs/conventions.md](docs/conventions.md). Instructions for AI
agents: [AGENTS.md](AGENTS.md).
