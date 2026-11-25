# Ticket Classifier

Classifies support tickets into a category (`billing`, `technical`, `account`, `other`)
and a priority (`low`, `medium`, `high`) with Claude, as a LangGraph workflow:

```
START → get_customer → retrieve_knowledge → triage → draft_reply → high priority? → human_review → END
                                                                          else → mark_handled → END
```

- `get_customer` reads the customer from `CUSTOMERS_PATH` (if the ticket has an id).
- `retrieve_knowledge` finds the policy passages closest in meaning to the ticket
  text (see [Knowledge base](#knowledge-base)). `triage` gets them in the prompt.
- `triage` makes one structured-output call to Claude. No classification (refusal,
  `max_tokens`) fails the ticket; the next run retries it.
- `draft_reply` makes a second call and drafts a reply to the customer from the
  passages, with the API's citations: `[1]` after each cited part and the sources at
  the end. Without passages the reply cites nothing and states no policy. The draft
  is never sent; a person does that. No usable reply fails the ticket; the next run
  continues at `draft_reply` and keeps the saved classification.
- `human_review` pauses the run until a person answers (see below).
- Each ticket is its own thread; runs are saved in SQLite and survive a crash or exit.
- Every workflow event (node update, pause, finish) is appended as one JSON line to
  `TRACE_FILE` (default `output/trace.jsonl`), with `ticket_id`, `node`, `event` and
  `data`. This file holds ticket, customer and reviewer text; it stays local and is
  not sent to the monitoring stack. The graph is saved as mermaid to `GRAPH_PATH`.

## Setup

```sh
make setup                      # uv sync
cp .env.example .env            # then set ANTHROPIC_API_KEY and KNOWLEDGE_DATABASE_URL
cp database/.env.example database/.env   # then set POSTGRES_PASSWORD
make db-up                      # PostgreSQL with pgvector on localhost:5432
make kb-index                   # embed the knowledge base; downloads the model once
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
classification, the policy passages triage saw, the draft reply) and the command to
answer:

```sh
uv run ticket-classifier resume T-3 --approve --note "Dana takes it"
uv run ticket-classifier resume T-3 --decline --note "Bot can answer"
make approve TICKET=T-3 NOTE="Dana takes it"   # same, via make
make decline TICKET=T-3 NOTE="Bot can answer"
```

A resume needs only the ticket id (the saved run has the ticket), finishes only that
ticket, makes no model call (the reply is drafted before the pause) and adds its
result to
`results.json` without removing the others. `--approve` gives `escalated: true` with
the note as reason, `--decline` gives `escalated: false`. Paused tickets are not in
`results.json` until they are answered; a normal run leaves them paused.

A second `run` does not classify finished tickets again: it reuses their saved result
(no model call) and continues crashed runs where they stopped. To classify everything
again, run `make reset` (deletes saved runs, trace and results; paused tickets are lost).

While a run works, nodes emit progress events (e.g. `calling model`), logged as
`[custom]` lines. `LOG_LEVEL=DEBUG` also logs every state update.

Exit code: `0` every ticket got a result or is paused for a human, `1` some tickets
failed (the rest are still saved), `2` input could not be loaded, the knowledge base
is not ready, or the ticket to resume has no paused run.

`run` checks before the first ticket, so no API call is spent: `ANTHROPIC_API_KEY`
set, database reachable, model downloaded, index built. Each missing piece stops with
exit code `2` and names the fix (`make db-up`, `make kb-index`). `resume` needs neither
key nor database. An invalid setting (e.g. `LOG_LEVEL=LOUD`) stops at startup with a
traceback.

**Input** (`fixtures/tickets.json`): list of `{"id", "text", "customer_id"?}`.
Customers are read from `CUSTOMERS_PATH` (JSON object keyed by customer id).

**Output** (`output/results.json`, git-ignored):

```json
[{"ticket_id": "T-1", "customer_id": "1001", "category": "billing",
  "priority": "high",
  "reply": {"text": "... are refunded in full. [1]\n\nSources:\n[1] billing.md, part 4",
            "citations": [{"source": "billing.md", "ordinal": 4,
                           "quotes": ["... refunded in full."]}]},
  "escalated": false, "escalation_reason": null}]
```

`quotes` holds the `cited_text` the API returned for each citation.

## Knowledge base

Policy documents in `KNOWLEDGE_BASE_PATH` (default `data/knowledge_base/`, one `.md`
file per policy) are cut into word chunks, embedded locally with fastembed
(`BAAI/bge-small-en-v1.5`, 384 dimensions, no PyTorch, no API) and stored in
PostgreSQL with pgvector ([database/docker-compose.yml](database/docker-compose.yml)).

```sh
make db-up / db-down / db-check   # start, stop (data is kept), check pgvector
make kb-index                     # embed; skipped if the documents are unchanged
make kb-eval                      # compare chunk settings on labelled questions
```

- One index per model and chunk setting (`CHUNK_SIZE`, `CHUNK_OVERLAP`), so settings
  sit side by side. `kb-index` stores a hash of the documents and embeds only when it
  changed.
- `retrieve_knowledge` embeds the ticket text and takes the `KNOWLEDGE_TOP_K` closest
  chunks by cosine similarity (`<=>`, exact search). Passages below
  `KNOWLEDGE_MIN_SCORE` (default 0.65) are left out and only counted; the prompt
  says passages can be unrelated.
- Only `kb-index` may download the model (to `EMBEDDING_CACHE_PATH`); `run` loads it
  from there. Hugging Face telemetry is turned off.
- Telemetry gets passage and dropped counts, citations (`refunds.md#2`) and scores,
  and for the reply its citation count and sources; never passage, ticket or reply
  text.
- `kb-eval` measures hit@1, hit@3 and mean reciprocal rank for vector search and
  PostgreSQL full-text search, on `data/eval/knowledge_questions.json`. Each setting
  gets its own index; `run` keeps using the configured one. It also compares minimum
  scores (`--thresholds`): answers kept versus unanswerable questions left without
  a passage.

Results of the experiments (chunk sizes, minimum score, column types, full-text
search, HNSW): [docs/exercises/plan_w9d1.md](docs/exercises/plan_w9d1.md).

## Observability

Traces, metrics and logs go to a local Docker stack (OpenTelemetry Collector, Tempo,
Prometheus, Loki, Grafana). Telemetry is off by default.

```sh
make obs-up                     # start the stack
make obs-check                  # all services ready?
OTEL_ENABLED=true make run      # calls the Anthropic API
```

Dashboards (user `admin`): [metrics](http://localhost:3000/d/ticket-classifier),
[traces](http://localhost:3000/d/ticket-classifier-traces),
[logs](http://localhost:3000/d/ticket-classifier-logs). Set `OTEL_ENABLED=true` in
`.env` to keep telemetry on. Details, diagrams and a query cookbook:
[monitoring/README.md](monitoring/README.md).

## Configuration

Environment variables or `.env`, see [.env.example](.env.example):
`ANTHROPIC_API_KEY` (required for `run`), `MODEL`, `MAX_TOKENS`, `REPLY_MODEL`
(default: `MODEL`), `REPLY_MAX_TOKENS`, `LOG_LEVEL`, `LOG_FILE`,
`TRACE_FILE`, `TICKETS_PATH`, `CUSTOMERS_PATH`, `RESULTS_PATH`,
`CHECKPOINT_PATH`, `GRAPH_PATH`.

Knowledge base: `KNOWLEDGE_DATABASE_URL` (required for `run` and `kb-index`),
`KNOWLEDGE_BASE_PATH`, `EMBEDDING_MODEL`, `EMBEDDING_CACHE_PATH`, `CHUNK_SIZE`,
`CHUNK_OVERLAP`, `KNOWLEDGE_TOP_K`, `KNOWLEDGE_MIN_SCORE`, `KNOWLEDGE_QUESTIONS_PATH`.
PostgreSQL credentials: `database/.env`.

OpenTelemetry (off by default): `OTEL_ENABLED`, `OTEL_SERVICE_NAME`,
`OTEL_EXPORTER_OTLP_ENDPOINT` (empty prints to the console),
`OTEL_RESOURCE_ATTRIBUTES`. The local stack: [monitoring/README.md](monitoring/README.md).

## Layout

| Module | Role |
| --- | --- |
| `cli.py` | entry point: dispatch to a command, exit codes |
| `args.py` | subcommands `run`, `resume`, `kb-index`, `kb-eval`, each parsed into a typed object |
| `commands.py` | what the subcommands do: open knowledge base and checkpointer, build graph, run, save results, index, evaluate |
| `checkpoint.py` | SQLite checkpointer that loads only known state types |
| `runner.py` | run each ticket in its own thread (streamed), resume paused or crashed runs, collect failures |
| `graph.py` | build the workflow, write the mermaid diagram |
| `context.py` | runtime context of a run (the knowledge base), not saved in checkpoints |
| `knowledge/` | `documents.py`, `chunking.py`, `embedder.py` (fastembed), `store.py` (PostgreSQL), `evaluation.py` (kb-eval) |
| `nodes/` | one file per node, the router, the node names |
| `prompts.py`, `client.py` | system prompts and user messages (triage, reply), Anthropic client |
| `replies.py` | build the `Reply` from the API answer: citation numbers, markers, source list |
| `customers.py` | customer data access (swap for a DB later) |
| `storage.py` | read tickets, write or merge results |
| `trace.py`, `logging_config.py` | JSON lines trace, logger setup |
| `telemetry.py` | OpenTelemetry: settings to the SDK, start TraceVerde, send our logs |
| `models/` | data only: `domain.py` (input), `state.py` (graph state), `results.py` (output rows), `knowledge.py` (chunks, passages, retrieval result, labelled questions), `reply.py` (draft reply, citations) |
| `config.py` | settings |

## Development

```sh
make test            # pytest, no API calls, no database
make test-db         # tests against PostgreSQL (database knowledge_test)
make test-embedding  # the one test with the real embedding model
make reset           # delete saved runs, trace and results
make lint            # ruff and mypy (strict, src only)
make format
```

Code conventions: [docs/conventions.md](docs/conventions.md). Instructions for AI
agents: [AGENTS.md](AGENTS.md).
