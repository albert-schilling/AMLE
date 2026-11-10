# Ticket Classifier

Classifies support tickets into a category (`billing`, `technical`, `account`, `other`)
and a priority (`low`, `medium`, `high`) with Claude. If a ticket has a customer id,
the model looks the customer up (tool use) before deciding.

## Agent loop

Per ticket the model runs a capped loop: reason, call a tool, observe, repeat, until
it gives a final answer. Tools: `lookup_customer` (read-only) and `escalate_to_human`.

- Every Thought, Action and Observation is printed, followed by the final answer.
- `escalate_to_human` only counts after a human types `y` at the console prompt. A
  rejection goes back to the model as a normal observation and the loop continues.
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
```

Calls the Anthropic API and may incur charges. Exit code: `0` all classified,
`1` some tickets failed (the rest are still saved), `2` input could not be loaded.

**Input** (`fixtures/tickets.json`): list of `{"id", "text", "customer_id"?}`.
Customers are read from `CUSTOMERS_PATH` (JSON object keyed by customer id).

**Output** (`output/results.json`, git-ignored):

```json
[{"ticket_id": "T-1", "customer_id": "1001", "category": "billing",
  "priority": "high", "escalated": false, "escalation_reason": null}]
```

## Configuration

Environment variables or `.env`, see [.env.example](.env.example):
`ANTHROPIC_API_KEY` (required), `MODEL`, `MAX_TOKENS`, `MAX_ITERATIONS`, `LOG_LEVEL`,
`TICKETS_PATH`, `CUSTOMERS_PATH`, `RESULTS_PATH`.

## Layout

| Module | Role |
| --- | --- |
| `cli.py` | argument parsing, exit codes |
| `batch.py` | classify many tickets, collect failures |
| `classifier.py` | one ticket → Claude tool runner → classification |
| `prompts.py` | system and user prompts |
| `approval.py`, `trace.py` | human approval prompt, trace printing |
| `tools.py` | tools the model can call |
| `customers.py` | customer data access (swap for a DB later) |
| `storage.py` | read tickets, write results |
| `models.py`, `config.py` | pydantic models and settings |

## Development

```sh
make test      # pytest, no API calls
make lint
make format
```
