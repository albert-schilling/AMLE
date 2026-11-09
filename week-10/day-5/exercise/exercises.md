# W10D5 Exercise — Integration Patterns Across the Modern Stack

## Scenario

All week, ScoutBot gained one new power a day, and each proved itself alone: an MCP **client** (Day 1, call
a tool it did not write), an MCP **server** (Day 2, publish its own tools), pre/post-tool-use **hooks** and
a research **subagent** (Day 3), and a type-safe **triage agent** (Day 4). Four good pieces — none of which
has ever run together.

Today is the finale, and it invents nothing new: the day is the **assembly**. You add one module,
`stack.py`, that wires the week's collaborators into one run and executes the integration pattern —
**classify with a contract, then resolve with tools.** The happy accident that makes this short is that
`run_agent_loop` was additive from the start: `mcp`, `hooks`, `ledger`, and `subagent` are *already*
optional arguments. So `assemble_stack` mostly gathers collaborators, and `resolve_ticket` runs the Day 4
typed triage first, then the fully-wired loop.

The theme: a production agent is a **composition of small, separately-tested patterns**. You prove the
composition **offline** (a `TestModel` triage, a patched loop client, stubs), and you write down a
**decision guide** — the transferable idea of the whole week — matching a problem to the pattern that solves
it.

## Starting point

`scoutbot-baseline/` is **your finished Day 4 agent — the typed triage agent.** Everyone extends this same
baseline, in place. Three things to know:

- **Everything you need already exists.** `run_agent_loop` accepts `mcp`, `hooks`, `ledger`, `subagent`,
  `log_path`; `typed_agent.triage(text, model=None)` produces the contract; `refund_guard`/`audit_hook`,
  `Ledger`, `ResearchSubagent`, and `MCPToolProvider` are all built. You are *wiring*, not building.
- **The triage model is an argument.** `resolve_ticket(..., triage_model=None)` passes the model down to
  `typed_agent.triage`. Tests pass a `TestModel`; the demo passes `None` and gets the real one. Never bind a
  real model into the composition.
- **Billing facts come from the account.** The refund guard's `get_customer` should be `look_up_customer` —
  the plan and recent-refund count are read from the customer record, never from what the model typed.

## Your task

Working in pairs, on a new branch.

### Part 1 — The assembly (`src/scoutbot/stack.py`)

1. **Define `Stack` and `StackResult`.** `Stack` holds the wired collaborators (`hooks`, `ledger`,
   `approve_fn`, `subagent`, `mcp`, and an `audit_trail` list). `StackResult` holds one run's output: the
   `triage` (a `TicketTriage`), the loop's `result` (an `AgentResult`), and the `audit_trail`.
2. **Write `assemble_stack(kb=None, approve_fn=None, ledger=None, mcp=None, get_customer=look_up_customer)`.**
   Build `Hooks(pre=[refund_guard(get_customer, approve_fn=approve_fn)], post=[audit_hook(trail)])`, default
   `ledger` to `Ledger.in_memory()`, and build a `ResearchSubagent(kb=kb)` **only when a `kb` is given**
   (otherwise `None`, so `research_policy` is not offered). Return a `Stack`. Every argument has a safe
   default.
3. **Write `resolve_ticket(stack, ticket_text, customer_id, ticket_id=None, triage_model=None,
   log_path=None, max_steps=6)`.** Two moves: (a) `triage = typed_triage(ticket_text, model=triage_model)`,
   then (b) `run_agent_loop(ticket_text, customer_id, approve_fn=stack.approve_fn, mcp=stack.mcp,
   hooks=stack.hooks, ledger=stack.ledger, subagent=stack.subagent, …)`. Return
   `StackResult(triage, result, stack.audit_trail)`.
4. **Export the new pieces** from `__init__.py` (`Stack`, `StackResult`, `assemble_stack`, `resolve_ticket`).

### Part 2 — A demo, and offline tests (`run_stack.py`, `tests/test_stack.py`)

5. **See it work (`run_stack.py`).** Build a real stack — a `KnowledgeBase` for the subagent, an
   `stdio_provider` to the order-status server for `mcp`, a real approver — and run one ticket that touches
   several seams (an account lookup, a refund large enough to trip the guard, an order the MCP tool can
   check). Print the triage, each loop step, the audit trail, the ledger, and the final answer. This path
   makes real calls, so it needs a key — the *offline* proof lives in the tests.
6. **Set the backstop first.** At the top of `tests/test_stack.py`, set
   `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` (in case the module runs before `test_typed_agent`).
7. **Test the pattern.** Patch `scoutbot.loop._client` to script the loop's turns, and pass a
   `TestModel(custom_output_args={…})` as `triage_model`. Assert `resolve_ticket` returns a `StackResult`
   whose `triage` is a `TicketTriage` with your values, and whose `result.final_answer` is your scripted
   final.
8. **Test the guarded refund end-to-end.** Script the loop to call `issue_refund` for a customer + amount the
   policy blocks (e.g. `1001`, `900`). With `approve_fn=lambda r: False`, assert the observation is blocked,
   the **audit trail recorded the veto**, and the **ledger moved no money**. Then with `approve_fn=lambda r:
   True`, assert it issued once — and that a *second* identical call is **idempotently skipped** (ledger has
   one entry).
9. **Test that the pieces compose.** Add a `FakeMCP` provider (duck-typed `tool_schemas`/`has_tool`/`call`)
   and assert an MCP tool is both **offered** to the model and **dispatched**. Add a `StubKB` and assert
   `research_policy` is offered and returns a contracted result. Assert `assemble_stack(kb=None).subagent is
   None`.
10. **Same habit as every day**: bump the version in `pyproject.toml`, keep the whole earlier suite green,
    commit on your branch, open a PR.

### Part 3 — The decision guide (`DECISIONS.md`)

11. **Write a short decision guide** — the day's transferable deliverable. In a table, map at least the
    week's six problems to their patterns, each with a one-line justification:

    | When you need… | Reach for | Why |
    | --- | --- | --- |
    | a tool you didn't write | an MCP client | it lives in another program; call it over the protocol |
    | it must not run unless allowed | a pre-tool-use guard | authorisation belongs in code, not the prompt |
    | it must run at most once | an idempotent ledger | a stable key makes a retry a no-op |
    | a validated final answer | a typed `output_type` | the framework enforces the contract |
    | a scoped side-question answered | a subagent | delegate it and get a contract back |
    | to see what happened | an audit post-hook + a trace | witness every call, blocked or not |

    Then add **one row of your own** for a problem ScoutBot does *not* yet solve, and name the pattern you
    would reach for. The skill is naming the *problem* precisely; the pattern is almost a lookup.

> **One gotcha worth naming.** If your tests need a key, something bound a real model into the composition —
> almost always `resolve_ticket` calling `typed_agent.triage` without threading `triage_model` through. The
> model is an argument; a `TestModel` slots into the same seam.

## Expected outcome (minimum requirements)

- [ ] **`assemble_stack`** wires the week's collaborators (hooks, ledger, subagent, mcp) with safe defaults
- [ ] **`resolve_ticket`** runs classify-then-resolve: the typed triage first, then the fully-wired loop
- [ ] **A `StackResult`** bundles the triage, the loop result, and the audit trail
- [ ] **A demo (`run_stack.py`)** flows one ticket through the whole stack
- [ ] **Offline tests (`tests/test_stack.py`)** prove the composition with a `TestModel` triage + patched
      `_client` + stubs, under `ALLOW_MODEL_REQUESTS = False`
- [ ] **A guarded refund is proven end-to-end** — blocked-then-audited, and idempotent when approved
- [ ] **A decision guide (`DECISIONS.md`)** maps at least the six problems to patterns, plus one of your own
- [ ] **The whole earlier suite still passes** — the stack is additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Wire ScoutBot's own MCP server into the stack.** Instead of the order-status server, point `mcp` at
  `scoutbot_mcp_server.py` (Day 2). Watch the name clash: `look_up_customer` is both a native tool *and* a
  published one. What breaks, and what does that tell you about tool namespaces across a protocol?
- **Feed the triage into the resolution.** Right now the triage rides alongside the loop. Use its
  `priority`/`category` to shape the loop — e.g. raise `max_steps` for an `urgent` ticket, or seed the first
  message with the category. Keep it offline-testable.
- **A trace assertion.** Pass a `log_path` in a test and assert the JSONL trace has one line per step. Now
  your test proves the *observability* seam composes too.
- **A second stack shape.** Build a "read-only" stack — no ledger, so `issue_refund` is not even offered —
  and assert the model cannot move money at all. One `assemble_stack` call, a very different safety posture.
- **Route the decision guide back into code.** Turn one row of `DECISIONS.md` into a tiny helper (a function
  that, given a problem tag, names the pattern) and test it. Notice you are now encoding judgment, not just
  documenting it.

## If you're running out of time

Protect Part 1 (the `assemble_stack` + `resolve_ticket` assembly) and steps 7–8 (the pattern test and the
guarded-refund test). That core — the week's pieces wired into one classify-then-resolve run, proven offline
with a guarded refund — is what the day is assessed on. Trim the compose tests (step 9) and the decision
guide's "your own row" first, but flag whatever you skipped rather than quietly leaving it out. Do **not**
let `resolve_ticket` call a real triage model to save time: a key-required test defeats the offline design.
(Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
