# W08 D5 - Observability plan

Local only stack, no cloud:

```text
app (TraceVerde + OTel SDK) → OTel Collector → Prometheus (metrics)
                                             → Tempo (traces)
                                             → Loki (logs)
                                                   ↓
                                                Grafana
```

Prometheus stores only metrics, so traces go to Tempo. Loki 3 takes OTLP directly at
`/otlp`; the collector's old `loki` exporter is gone, use `otlphttp` instead.

## Phase A: stack alone, no app changes

1. [x] `monitoring/docker-compose.yml`: pinned image versions, ports on `127.0.0.1`
   only, two networks (internal backend, normal frontend), named volumes.
2. [x] Collector config: OTLP receiver on 4318 (HTTP) and 4317 (gRPC). Pipelines:
   metrics → Prometheus, traces → Tempo, logs → Loki (`otlp_http` to
   `http://loki:3100/otlp`).
3. [x] Prometheus with the OTLP (or remote-write) receiver on, data on a volume.
4. [x] Tempo with local storage on a volume, plus the metrics generator (span metrics
   and service graphs, pushed to Prometheus by remote write).
5. [x] Loki single binary: filesystem storage on a volume, `tsdb` schema v13, OTLP
   ingestion, `ticket_id` as structured metadata (not a label), 14 day retention.
6. [x] Grafana with a volume and provisioned data sources. Links: Tempo → Loki (logs
   for a span, by `trace_id`), Loki → Tempo (derived field on `trace_id`),
   Tempo → Prometheus (span metrics, service map), Prometheus → Tempo (exemplars).
7. [x] `make obs-up` / `make obs-down` / `make obs-check` / `make obs-usage`
   (volume sizes). Check Grafana :3000 and the collector :13133 from the host;
   Prometheus, Tempo and Loki from inside the network (they have no host ports).
   Check Grafana's phone-home settings applied.

Privacy: Prometheus, Tempo and Loki sit on an `internal` Docker network (no internet
access, tested). Only the collector and Grafana are on the normal network. Usage
reports are off in Tempo, Loki and Grafana.

Storage: 14 days in Prometheus (also max 1 GB), Tempo and Loki. Diagrams and details:
[monitoring/README.md](../../monitoring/README.md).

## Phase B: TraceVerde and OTel in the app

8. [x] `uv add "genai-otel-instrument[anthropic,langgraph]"` (1.48.1). Installs and
   imports on Python 3.14. Source audit: own usage telemetry is opt-in
   (`TRACEVERDE_TELEMETRY`, off, no default URL); content capture (prompts, answers)
   is off by default; the only other network use is a local check whether a collector
   listens on `localhost:4318`.
9. [x] Settings: `OTEL_ENABLED` (default off), `OTEL_SERVICE_NAME`,
   `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_RESOURCE_ATTRIBUTES` in `config.py` and
   `.env.example`. The SDK reads only `os.environ`, not `.env`: step 10 hands the
   settings to it. `service.version` comes from the package version.
10. [x] `telemetry.configure_telemetry()` in `cli.main`: writes the settings to
    `os.environ`, then calls `genai_otel.instrument()`. TraceVerde wraps the Anthropic
    client's `__init__`, so only the client (lazy) must come after it, not the
    import. Fixed: content capture off, no external egress, air gapped, only the
    `anthropic` and `langgraph` instrumentors, no GPU/MCP, exemplars on
    (`trace_based`). Tests mock `instrument`.
11. [x] Logs: TraceVerde sets up no log provider, so `telemetry.attach_log_handler`
    adds the `LoggingHandler` from `opentelemetry-instrumentation-logging` (the SDK's
    own is deprecated) to the `ticket_classifier` logger only: no SDK export logs
    (no feedback loop), no TraceVerde or Anthropic logs. Same resource as the
    traces. Records carry `trace_id` and `span_id`; `extra={...}` fields become
    attributes. The console handler stays.
12. [x] Console first: an empty endpoint prints spans to stdout. Test with `resume`
    (no API cost). Result: span `langgraph.graph.stream` with child
    `langgraph.node.human_review`; TraceVerde sets `session.id` = thread id = ticket
    id. Only the log written inside the node has a `trace_id`; logs from the runner
    and commands are outside any span (`trace_id` 0), so step 14 needs our own root
    span per ticket. Metrics: `gen_ai.requests` plus TraceVerde's unused
    `gen_ai.server.*` gauges.
13. [x] Point the endpoint at the collector. Check spans in Tempo, logs in Loki, and
    the jump from a log line to its trace.

## Phase C: what to measure

14. [x] Our own spans, two levels: a root span per CLI command (`run`, `resume`) and
    a child span per ticket in `runner.py`. TraceVerde's graph and node spans hang
    below. Then every log line of a command has a `trace_id`, also the batch
    summary. Node spans come from TraceVerde; no logging or span code in nodes.
    Checked in Tempo and Loki: all log lines of a resume share the trace id and
    point to the right span. A failed ticket's span is ERROR.
15. [x] Ticket span attributes: `ticket_id`, `thread_id`, `category`, `priority`,
    `run_mode` (`run` or `resume`). `ticket_id` and `thread_id` also on every log line
    inside the ticket span, automatically (logging filter + `contextvar`, no `extra=`
    by hand). This links `run` and `resume` of one ticket in Loki, across two traces.
    Checked in Tempo and Loki with a `run` without model calls. Not yet checked: one
    ticket's `run` and `resume` lines together in Loki.
16. [x] Tokens and cost in Prometheus: the Anthropic SDK writes its own spans, so
    TraceVerde records no token metrics. The collector's `signal_to_metrics`
    connector derives `llm_calls_total`, `llm_input_tokens_total`,
    `llm_output_tokens_total` and `llm_cost_usd_total` from the span attributes.
    Privacy: no `traceparent` header to Anthropic; only INFO and above go to Loki;
    lines with ticket, customer or reviewer text are `CONSOLE_ONLY`. Checked with
    the real app against a fake API. Open: TraceVerde's unused `gen_ai.server.*`
    gauges are still exported.
17. [x] Human in the loop: a pause is not an error. The ticket span gets
    `ticket.status=paused` and, when the run pauses, a `paused` event with the node.
    TraceVerde does not mark `interrupt()` as an error either, so the error rate
    stays clean. Find waiting tickets with `{span.ticket.status="paused"}`.
18. [x] `trace.jsonl` stays a local file and is not sent to Loki: its `data` holds full
    graph states with ticket, customer and reviewer text. Loki has the workflow lines,
    Tempo the node timing.

## Phase D: dashboard and tests

19. [x] Provisioned Grafana dashboard `monitoring/grafana/dashboards/ticket-classifier.json`:
    ticket runs, paused, resumed, failed, error rate, cost, tickets by category and
    priority, p95 latency per node, model calls, tokens, warnings and errors with a
    `ticket_id` filter. Ticket spans carry `ticket.status` (`finished`, `paused`,
    `failed`); `ticket.reused` marks runs that did no work, which are not counted.
    Prometheus stores the connector's deltas as is (`otlp-native-delta-ingestion`,
    experimental), so these metrics use `sum_over_time`, not `increase`.
20. [x] Tests with `InMemorySpanExporter` and `InMemoryLogRecordExporter`: span names
    and attributes, log records with `ticket_id` and `trace_id`, exporter choice, no
    private text in spans or logs. No API call.
21. [x] README: start the stack, URLs, env vars, log to trace navigation.

Steps 1-13 need no API calls. Token and cost metrics need `make run` (costs money).
