# Strengths

- Small modules with one job each.
- Discriminated unions (`Resolved | Escalated`, `ResolvedTicket | EscalatedTicket`) make
  impossible states impossible to build or load.
- The human gate is injected as an `approve` callable, so it is easy to test.
- Untrusted input is fenced in `<ticket>` tags; trusted reference URLs stay outside.
- `safe_fetch.py` is careful: https only, allowlist, no redirects, private address
  check, timeout, size cap, content-type filter. The DNS rebinding gap is documented.
- Comments explain *why*, not *what*.
- Tests run without API calls and are fast.
