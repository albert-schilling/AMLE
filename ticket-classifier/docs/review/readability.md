# Readability

## Naming

- `log_file` is where *our* logs go; `log_path` and `log_file_id` are the *input* log
  uploaded to the sandbox. Rename to `attached_log_path` / `attached_log_id`.

## Duplication

- `status_domain` + `status_url` and `payments_domain` + `payments_url` repeat the same
  host. Derive the domain with `urlsplit(url).hostname`.
- ~~`to_classified_ticket` reads the classification two ways~~ — gone with
  architecture item 4.
- [trace.py](../../src/ticket_classifier/trace.py):
  - the `tool_use` and `server_tool_use` branches in `log_actions` are identical; merge.
  - server result handling (`web_fetch_tool_result`, code results) is repeated in
    `log_actions` and `step_observation`; use one helper.

## Order and layout

- `CODE_RESULT_TYPES` in `trace.py` is defined after the function that uses it. Move it
  to the top.
- [config.py:32-34](../../src/ticket_classifier/config.py#L32-L34): the `log_path`
  default is split over three lines by the formatter. Put the comment on its own line.

## Small cleanups

- `run_once` in `evals.py` has no type hints.
- `safe_fetch.fetch_text` builds the body with `body += chunk`; use a `bytearray`.
- The content-type check in `safe_fetch` is case-sensitive; lower-case the header first.
- `__init__.py` exports `classify` but not `Resolved` / `Escalated`, which it returns.
