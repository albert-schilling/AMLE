# Docs and structure

## README is out of date

- Tools list names only `lookup_customer` and `escalate_to_human`. Missing:
  `web_fetch`, `find_duplicate_charges`, `code_execution`.
- Layout table is missing `payments.py`, `safe_fetch.py`, `evals.py`.
- Configuration list is missing `FETCH_BACKEND`, `STATUS_DOMAIN`, `STATUS_URL`,
  `PAYMENTS_DOMAIN`, `PAYMENTS_URL`, `WEB_FETCH_MAX_USES`,
  `WEB_FETCH_MAX_CONTENT_TOKENS`, `LOG_PATH`.
- `make eval` is not mentioned (it is described in [../evals.md](../evals.md)).

## Agent instruction files are copies

`CLAUDE.md` and `AGENTS.md` have the same content and will drift. Make `CLAUDE.md`
contain only `@AGENTS.md`.

## No check that thinking mode fits the model

Already in TODO. Setting `MODEL` to a Claude 4.7+ model with `THINKING_BUDGET > 0` gives
a 400 on every ticket. A validator in `Settings` (or a startup warning) would fail
fast instead.
