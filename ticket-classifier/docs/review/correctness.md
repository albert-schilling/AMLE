# Correctness

## 1. Missing API key crashes with a traceback — accepted

A bad configuration stops the program at startup with a traceback and exit code `1`.
Failing fast is fine; the README now says so. `tools.py` builds `WEB_FETCH_TOOL` from
the settings at import, so the crash happens on import.

## 2. Evals do not check the log file and write to the real trace

[evals.py:117](../../src/ticket_classifier/evals.py#L117) uploads `log_path` without
checking that it exists (the CLI checks first). Eval runs also append to the real
`TRACE_FILE`, so eval and production traces mix.

Fix: check `log_path.exists()` like the CLI; point `trace_file` to a separate file
for evals (e.g. `output/eval_trace.jsonl`).

## 3. Missing or broken customers file breaks the tool

[tools.py:27](../../src/ticket_classifier/tools.py#L27) only catches `ValidationError`.
A missing `customers.json` (`OSError`) or invalid JSON (`json.JSONDecodeError`) escapes
`lookup_customer`.

Fix: catch these too and return "Customer record unavailable".

## 4. Already in TODO

- Cap path drops an approved escalation (TODO bug 1).
- Auth errors repeat for every ticket (TODO bug 2).
