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

14. [ ] Our own spans, two levels: a root span per CLI command (`run`, `resume`) and
    a child span per ticket in `runner.py`. TraceVerde's graph and node spans hang
    below. Then every log line of a command has a `trace_id`, also the batch
    summary. Node spans come from TraceVerde; no logging or span code in nodes.
15. [ ] Ticket span attributes: `ticket_id`, `thread_id`, category, priority, run vs
    resume. `ticket_id` and `thread_id` also on every log line inside the ticket span,
    automatically (logging filter + `contextvar`, no `extra=` by hand). This links
    `run` and `resume` of one ticket in Loki, across two traces.
16. [ ] Tokens and cost: `gen_ai.client.inference.usage.*` and
    `gen_ai.usage.cost.total` in Prometheus. Turn off TraceVerde's unused
    `gen_ai.server.*` gauges if possible.
17. [ ] Human in the loop: either the `interrupt()` pause is an error span on purpose,
    or a `paused` span event plus a log line.
18. [ ] `trace.jsonl`: `trace_event()` becomes a structured log record (`ticket_id`,
    `node`, `event` as attributes) sent to Loki; keep the file as a fallback switch.

## Phase D: dashboard and tests

19. [ ] Provisioned Grafana dashboard (JSON): tickets per category and priority,
    latency per node, tokens and cost per run, paused count, Loki panel with
    warnings and errors filtered by `ticket_id`.
20. [ ] Tests with `InMemorySpanExporter` and `InMemoryLogExporter`: span names and
    attributes, log records with `ticket_id` and `trace_id`. No API call.
21. [ ] README: start the stack, URLs, env vars, log to trace navigation.

Steps 1-13 need no API calls. Token and cost metrics need `make run` (costs money).
