# W8D5 observability cleanup

Open items from the review of the two observability commits. Batch 1 (privacy and
crashes) and the safe log check are done.

## Batch 2: correct metrics

- [ ] Rejected resumes must not count as "Resumed". Check that the ticket is paused
      before opening its span, or exclude these spans from the metric.
- [ ] Compute the ticket error rate from `tickets_runs_total`, so reruns of finished
      tickets do not dilute it.
- [ ] Count every exception that leaves `ticket_span` as `failed`. Keep `record_failure`
      for caught errors, so the failure log line keeps its `ticket_id` and span.

## Batch 3: tests

- [ ] `test_debug_lines_are_not_exported`: restore the logger level afterwards.
- [ ] Client test: assert that the real HTTP request has no `traceparent` header.
- [ ] Add a test for rejected resumes.
- [ ] Add a test for unexpected exceptions in a ticket span.
- [ ] Add tests for the new safe log lines: pause, resume, human answer and customer
      not found. Assert that the reviewer note and customer id do not reach Loki.

## Batch 4: refactor

- [ ] Split `telemetry.py` into setup, logs and spans.
- [ ] Move OTel out of `cli.py`, for example into a `command_span()` helper.
- [ ] Use consistent attribute names: `ticket_id` and `run_mode` vs `ticket.status` and
      `ticket.reused`. Update the collector config, dashboards and README with them.
- [ ] Rename `trace.py`, for example to `event_log.py`, to avoid confusion with OTel
      traces.
- [ ] Add upper bounds to the new dependencies.
- [ ] Fix the mismatch between a custom `OTEL_SERVICE_NAME` and the service name
      hardcoded in the dashboards.

## Minor

- [ ] Drop TraceVerde's unused `gen_ai.server.*` gauges in the collector.
