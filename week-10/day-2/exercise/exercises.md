# W10D2 Exercise — Publish ScoutBot's Own Tools Over MCP

## Scenario

Yesterday ScoutBot borrowed a tool it didn't write. Today it lends two of its own. ScoutBot can search
the support policy and look up a customer — capabilities another team's agent would happily reuse. But
right now those tools are callable only from inside our loop, in Python. There is no door for anyone
outside to reach them.

Today you build that door. ScoutBot becomes an MCP **server**: a `FastMCP` program that publishes
`search_policy` and `look_up_customer` as tools, their schemas derived from type hints, so any client that
speaks the protocol can call them. Then you prove it the most satisfying way possible — by pointing
*yesterday's client* at *today's server* and watching it call ScoutBot's own tools, importing none of
ScoutBot's tool code.

The theme is the mirror of Day 1: same protocol, the provider's seat. And the discipline is the same as
every week — you keep it offline-testable by **injecting** the one collaborator that needs the network
(the knowledge base), so the whole server can be tested with a stub.

## Starting point

`scoutbot-baseline/` is **your finished Day 1 agent — the MCP client.** It already discovers and calls a
tool over MCP (`order_status_server.py`, `mcp_client.py`). Everyone extends this same baseline, in place.
Three things to know:

- **The type hints are the schema.** A `FastMCP` tool is a plain typed function — `search_policy(query:
  str, k: int = 3) -> list[dict]` — and the server derives its JSON schema from the hints. You do **not**
  hand-write an `input_schema` dict the way `tools.py` does. `order_status_server.py` is the exact shape to
  copy.
- **Publish what you have; don't reimplement it.** `look_up_customer` already exists in `tools.py`; your
  MCP tool should *call* it. `search_policy` should call the Week 9 `KnowledgeBase.search()`. The tool
  bodies are thin wrappers.
- **Inject the knowledge base so the tests stay offline.** `search_policy` needs a `KnowledgeBase`, which
  needs an embedding model. Make it an argument (`build_server(kb=...)`) so your tests can pass a stub with
  a fixed list of hits — no model, no SQLite, no network — reached over the in-memory transport.

## Your task

Working in pairs, on a new branch. No new dependency today — `mcp[cli]` arrived on Day 1.

### Part 1 — A tool server that publishes ScoutBot's capabilities (`scoutbot_mcp_server.py`, `mcp_server.py`)

1. **Write a `build_server(kb=None)` factory (`src/scoutbot/mcp_server.py`).** It creates a
   `FastMCP("scoutbot-tools")`, registers two tools on it with `@mcp.tool()`, and returns the server. Make
   the knowledge base an argument so it can be injected: leave it `None` for the real thing, pass a stub in
   tests.
2. **Publish `search_policy(query: str, k: int = 3) -> list[dict]`.** It calls the injected `kb.search(
   query, k=k)` (or a lazily-built process-wide default when `kb is None`) and returns each hit as a plain
   dict — `source`, `text`, `score`. The type hints are the schema; write **no** `input_schema`.
3. **Publish `look_up_customer(customer_id: str) -> dict`.** Have it *call* the existing
   `tools.look_up_customer` — the same function the native tool already uses. This is the point: you are
   publishing a capability, not rewriting it. Notice it now exists as both a native tool and an MCP tool.
4. **Add a stdio entrypoint (`scoutbot_mcp_server.py`).** A thin file at the project root: import the
   module-level `mcp` and call `mcp.run()` under `if __name__ == "__main__":`. Keep the server *logic* in
   the package (importable, testable); keep this file just the launcher, exactly as the package/entrypoint
   split lets you test without spawning a process.
5. **Lazily build the real knowledge base.** When `kb is None`, build or reopen the process-wide
   `knowledge.db` the first time `search_policy` runs (the same build-or-open the Week 9 demos do), so the
   import stays cheap and the model downloads at most once.

### Part 2 — Prove it, and test it offline (`run_mcp_server.py`, `tests/`)

6. **See it work (`run_mcp_server.py`).** Reuse **yesterday's** `stdio_provider` to launch
   `scoutbot_mcp_server.py` as a subprocess, discover its tools, and call both — `search_policy("how long
   until my refund arrives?")` and `look_up_customer("1001")`. Print the results. Import none of ScoutBot's
   tool code here: the whole point is that the client only speaks the protocol. (No Anthropic key needed —
   these are direct tool calls, not a reasoning loop.)
7. **Test the server offline (`tests/test_mcp_server.py`).** Write a tiny `StubKB` with a `search(query,
   k)` method that returns a fixed list of `Retrieved` hits — no embedder, no SQLite. Hand
   `build_server(kb=StubKB(...))` to `in_memory_provider` and assert: both tools are published; each
   schema came from the type hints (`k` is an integer defaulting to 3, `query`/`customer_id` required);
   `search_policy` returns the scored passages; `look_up_customer` returns the real record for a known id
   and `{"found": false, ...}` for an unknown one. **No subprocess, no network.**
8. **Pin the "written once" claim with a test.** Assert that the served `look_up_customer` returns exactly
   what the in-process `tools.look_up_customer` returns for the same id. Same capability, two doors.
9. **Same habit as every day**: bump the version in `pyproject.toml`, export the new pieces from
   `__init__.py`, commit on your branch, open a PR.

> **One gotcha worth naming.** A tool that returns a plain `dict` (like `look_up_customer`) comes back to
> the client differently from one that returns a `list` (like `search_policy`): the list arrives wrapped
> under a `"result"` key. Yesterday's `_result_to_observation` already handles both — but if you assert on
> the raw call result in a test, expect `obs["result"]` for the list-returning tool.

## Expected outcome (minimum requirements)

- [ ] **A `FastMCP` server** publishes `search_policy` and `look_up_customer`; both schemas come from type
  hints, not a hand-written dict
- [ ] **`build_server(kb=...)`** takes the knowledge base as an argument, so the server is offline-testable
- [ ] **The tools wrap existing capabilities** — `look_up_customer` calls `tools.look_up_customer`,
  `search_policy` calls `KnowledgeBase.search`; nothing is reimplemented
- [ ] **`scoutbot_mcp_server.py`** runs the server standalone over stdio; the server *logic* lives in the
  importable package
- [ ] **`run_mcp_server.py`** points yesterday's client at today's server and calls both tools, importing
  no ScoutBot tool code
- [ ] **Offline tests (`tests/test_mcp_server.py`)** stand the server up on the in-memory transport with a
  stub kb, and check schema-from-hints, both tools, and the served-equals-native claim
- [ ] **The whole earlier suite still passes** — publishing is additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Publish a third tool.** Expose something else ScoutBot can do (say, a read-only `recent_tickets(
  customer_id: str)` over the memory store) and confirm it appears in `tool_schemas()` with no other
  change.
- **Have ScoutBot consume its own server.** Point the Day 1 loop's `mcp` provider at
  `scoutbot_mcp_server.py` and let the model answer a ticket using the *published* `look_up_customer`
  instead of the native one. What is confusing about that, and what is clarifying?
- **Inspect your server with the MCP Inspector.** Run `mcp dev scoutbot_mcp_server.py` and click through
  the two published tools. Do the schemas match what your test asserts?
- **Return richer results.** Right now `search_policy` returns text and a score. What else might a client
  want (an id to cite, a URL)? Add a field and update the test — notice you never touch a schema dict.
- **Two servers, one client.** Run both `order_status_server.py` and `scoutbot_mcp_server.py`, and point a
  client at each. What does it mean that ScoutBot is now just one server among several?

## If you're running out of time

Protect steps 1–3 (the server and its two tools) and step 7 (the server tested in-memory with a stub kb).
That round-trip — ScoutBot's own capabilities published as MCP tools whose schema comes from type hints,
proven by a test that never spawns a process — is what the day is assessed on. Trim `run_mcp_server.py`
(step 6) and the served-equals-native test (step 8) first, and keep the knowledge base injected (step 1):
a server that builds a real `KnowledgeBase` inside the tool works but cannot be tested offline, and
offline-testability is half the point of the day. Flag whatever you skipped rather than quietly leaving it
out. (Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
