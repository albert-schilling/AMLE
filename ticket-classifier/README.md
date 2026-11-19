# Ticket Classifier

Classifies support tickets into a category (`billing`, `technical`, `account`, `other`)
and a priority (`low`, `medium`, `high`) with Claude. If a ticket has a customer id,
the model looks the customer up (tool use) before deciding.

## Agent loop

Per ticket the model runs a capped loop: reason, call a tool, observe, repeat, until
it gives a final answer. Tools: `lookup_customer` (read-only) and `escalate_to_human`.

- Every Thought, Action and Observation is logged (logger `ticket_classifier.trace`,
  plain format on the console), followed by the final answer. Set `LOG_FILE` to also
  write it, with timestamps, to a file (one record per line, newlines written as `\n`).
- Every step is also appended as one JSON line to `TRACE_FILE` (default
  `output/trace.jsonl`): ticket id, step, tool calls (name and input), observation, `duration_ms`,
  `errored`, token counts, `container_ms_estimate` (step time of code execution steps, an upper bound). A `final` line closes each ticket.
- The model may make only one tool call per turn, so an escalation can use the customer
  lookup result.
- `escalate_to_human` only counts after a human types `y` at the console prompt. A
  rejection goes back to the model as a normal observation and the loop continues.
- Extended thinking is on by default (`THINKING_BUDGET=2000`, must be >= 1024 and below
  `MAX_TOKENS`, default 4000); the model's thinking is logged as `Thinking:` lines. It
  costs extra tokens; set `THINKING_BUDGET=0` to turn it off.
- The loop is capped at `MAX_ITERATIONS` (default 6). Hitting the cap escalates the
  ticket automatically (`escalated: true`, no category/priority).

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

Calls the Anthropic API and may incur charges. The run is interactive: if the model
calls `escalate_to_human`, you get a `[y/N]` prompt (without a terminal it counts as
rejected).

### Human review of high-priority tickets

The workflow runs as a LangGraph graph: look up customer, triage, then route. A
high-priority ticket pauses in `node_wait_for_human` (`interrupt()`) and waits for a
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

Exit code: `0` every ticket got an outcome (a classification, or an escalation, which
has no category/priority), `1` some tickets failed (the rest are still saved), `2`
input could not be loaded.

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
`ANTHROPIC_API_KEY` (required), `MODEL`, `MAX_TOKENS`, `MAX_ITERATIONS`, `THINKING_BUDGET`, `LOG_LEVEL`,
`LOG_FILE`, `TRACE_FILE`, `TICKETS_PATH`, `CUSTOMERS_PATH`, `RESULTS_PATH`,
`CHECKPOINT_PATH`, `GRAPH_PATH`.

## Layout

| Module | Role |
| --- | --- |
| `cli.py` | argument parsing, exit codes |
| `batch.py` | run each ticket through the graph, resume paused or crashed runs, collect failures |
| `graph.py`, `nodes.py`, `triage_node.py` | LangGraph workflow: customer lookup, triage, pause for a human |
| `classifier.py` | one ticket → capped agent loop (Claude tool runner) → result row (`ResolvedTicket` or `EscalatedTicket`) |
| `prompts.py` | system and user prompts |
| `client.py` | Anthropic client, log file upload |
| `approval.py`, `trace.py`, `logging_config.py` | human approval prompt, trace logging, logger setup |
| `tools.py` | tools the model can call |
| `customers.py` | customer data access (swap for a DB later) |
| `storage.py` | read tickets, write or merge results |
| `models.py`, `config.py` | pydantic models and settings |

## Development

```sh
make test      # pytest, no API calls
make lint
make format
```

Code conventions: [docs/conventions.md](docs/conventions.md). Instructions for AI
agents: [AGENTS.md](AGENTS.md).
