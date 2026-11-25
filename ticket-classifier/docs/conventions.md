# Code conventions

## General

Write clean code for humans: code a reader understands on the first pass.

- **One job each.** Small modules and functions with a single responsibility. If a
  name needs "and", split it.
- **Few arguments.** App-wide singletons come from cached accessors
  (`get_settings()`, `get_client()`), not from argument chains; tests swap them via
  env vars and `cache_clear()` or a patch. Pass in only what the caller must choose,
  e.g. which checkpointer (SQLite or in-memory).
- **Fail loudly.** Catch only errors you can handle, never a bare `except Exception`.
  Return a clear error instead of a silent default.
- **No dead code.** No commented-out code, no unused helpers, no abstractions "just
  in case". Delete what is no longer used; git keeps the history.
- **Names say what something does.** Prefer a clear long name to a short vague one,
  and the same word for the same thing everywhere.

## Structure

- `models/` holds data only (pydantic models, TypedDicts, `Literal` types), no logic.
  Input in `domain.py`, graph state in `state.py`, output rows in `results.py`.
- One file per node in `nodes/`. Use node names only from `nodes/names.py`, never as
  string literals.
- Every run goes through `runner.run_thread`; a thread's status comes only from
  `checkpoint.run_status`.
- The checkpointer is passed to `build_workflow`, never created inside it.
- `cli.py` maps commands to exit codes; the work happens in `commands.py`.
- A command checks what it needs (API key, database, model, index) before the first
  ticket, so a missing piece costs no API call.
- Handles a node needs, like the knowledge base, come through the runtime context
  (`WorkflowContext`), not through the state: the state is saved in checkpoints.
- A new type in the graph state joins `CHECKPOINT_TYPES`, or it loads back as a plain
  dict.
- A `Protocol` lives with the code that uses it, not with the code that implements it.
- API citations and structured outputs cannot be combined (400 error). A call with
  citations uses `messages.create` without an output format, and our code builds the
  model from the answer.

## Logging

- `logger, safe_log = get_loggers(__name__)`: `logger` writes to the console only,
  `safe_log` also sends the line to Loki.
- Use `safe_log` only for ids, counts and labels: never file paths or ticket, customer,
  reviewer or error text. Policy passages: citations (`refunds.md#2`) and scores only,
  never their text or the query. Replies: citation counts and sources only, never the
  text or the quotes.
- For a caught error, log its type with `safe_log` and the full error with `logger`.

## Types

- Type everything where possible: arguments, return values, attributes. Use `Any`
  only where no real type exists.
- A type from a module that is imported lazily goes under `if TYPE_CHECKING:`.
- `make lint` runs mypy in strict mode on `src`. `# type: ignore[code]` or `cast` only
  where a library has no real type, with a comment saying why.
- A node returns `TriageUpdate` (only the keys it writes), never `TriageState`.
- A `TypedDict` has no defaults: mark keys that may be missing with `NotRequired`.
- Use a `dataclass` for internal objects, pydantic for data from outside (files, model
  output), a `TypedDict` where LangGraph needs a plain dict.

## Leading underscore

A leading underscore means one thing: **private attribute of a class** (pydantic
treats `_name` in a model as a private attribute).

- Module-level names get no underscore. Constants are `UPPER_CASE`
  (e.g. `TICKETS_ADAPTER = TypeAdapter(list[Ticket])`), helpers are plain `snake_case`.
- Module API is defined by `__all__` where it matters, not by underscores.
- Exception: pytest fixtures that are `autouse` and never requested by name
  (`_isolated_settings`).

## Tests

- Test behaviour: run the real graph (`InMemorySaver` or a SQLite file in `tmp_path`)
  and mock only the model, with the `model` fixture from `conftest.py` (it brings
  `reply_api` for the reply call; set `reply_api.return_value` to `reply_message(...)`
  for a reply with citations).
- Test behaviour, not the code's shape: a test must be able to fail when our code is
  wrong. No tests of constants, declarations, defaults or pydantic itself.
- Never import from `conftest.py`; shared test data goes in `tests/helpers.py`.
- Tests that need PostgreSQL are marked `postgres`, use the `knowledge_db` fixture
  (rolled back after each test) and run with `make test-db`; `make test` skips them.
  The knowledge base is faked with `FakeKnowledge` and `KeywordEmbedder`.

## Writing

- Code, comments, docs and commit messages in plain, short English.
- Comments say why, not what.
