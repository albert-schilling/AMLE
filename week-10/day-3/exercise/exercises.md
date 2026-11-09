# W10D3 Exercise — Guard a Tool With Hooks (and Meet a Subagent)

> **Career Session day.** This is the shorter, technical half of Wednesday. The hands-on is ~25 minutes,
> not the usual ~35 — the rest of the day is the Career Session. Build the guarded tool; the subagent is
> there to read and, if you have time, to wire.

## Scenario

Every tool ScoutBot has had so far only ever *reads* — it searches policy, looks up a customer,
retrieves passages. Those tools can be wrong, but they cannot do harm. Today ScoutBot gets its first
tool with a real-world effect: `issue_refund`, which moves money. And right now the model can call it as
freely as any other tool — no policy check, no human, nothing in the way.

Today you put something in the way. You wrap every tool call in two **hooks**: a pre-hook that runs
*before* the tool and can veto it, and a post-hook that runs *after* and records it. Then you write the
one guard that matters — `refund_guard` — which consults the Week 8 refund policy and asks a human to
approve anything large, and you make `issue_refund` itself **idempotent** through the Week 8 ledger, so
one approval can never pay twice.

The through-line: **put a checkpoint between the agent and something it should not blindly trust.** A
hook guards an *action*; a subagent's contract guards a *result*. Same instinct, twice.

## Starting point

`scoutbot-baseline/` is **your finished Week 10 Day 2 agent** — an MCP client and server both. Everyone
extends this same baseline, in place. Three things to know:

- **A hook is a plain callable.** Pre-hook: `(name, args) -> Optional[dict]` — return a dict to block
  (it becomes the observation), `None` to allow. Post-hook: `(name, args, observation) -> None` — it
  only watches. A `run_hooked(name, args, execute, hooks)` runs the pre-hooks, calls the tool if none
  vetoed, then runs the post-hooks either way.
- **The guard and the tool have separate jobs.** `refund_guard` (a pre-hook) owns policy and approval.
  `issue_refund` (the tool) owns the effect and its idempotency (the ledger). Do not fold the policy
  check inside `issue_refund` — the whole point is that the tool alone is not safe, and the hook is what
  guards it.
- **Inject what would otherwise need a human or the network.** The approver is an argument
  (`approve_fn`); the ledger is in-memory in tests; the subagent's knowledge base and synthesis are
  injected. That keeps every test offline and needs no key.

## Your task

Working in pairs, on a new branch. No new dependency today.

### Part 1 — The hook mechanism and a guarded refund (`hooks.py`, `tools.py`)

1. **Write the hook types and `run_hooked` (`src/scoutbot/hooks.py`).** Define a `PreHook`
   (`(name, args) -> Optional[dict]`), a `PostHook` (`(name, args, observation) -> None`), and a `Hooks`
   dataclass bundling `pre: list` and `post: list`. Then write `run_hooked(name, args, execute, hooks)`:
   run each pre-hook in order; if one returns a dict, that is the observation and `execute` is **not**
   called; otherwise call `execute()`; then run every post-hook with the final observation, **whether or
   not the tool was blocked.**
2. **Add the `issue_refund` tool (`src/scoutbot/tools.py`).** Give it a hand-written schema
   (`customer_id: str`, `amount: number`), and a `refund_key(customer_id, amount)` that builds a stable
   idempotency key. `issue_refund(customer_id, amount, ledger=None)` records the key in the ledger and
   performs the (mock) refund — and if the key is already present, it is a **no-op** that reports
   `skipped`. This is the idempotency, and it lives in the tool.
3. **Write `refund_guard` as a pre-hook (`src/scoutbot/hooks.py`).** A factory
   `refund_guard(get_customer, approve_fn, decide=...)` returns a pre-hook that **ignores every tool
   except `issue_refund`** (returns `None` so they run). For a refund, it reads the customer, applies the
   Week 8 refund policy (`policy.py`), and for anything at or above the limit calls `approve_fn(reason)`.
   No approval → return a block dict (`{"blocked": True, "reason": ...}`); approved and within policy →
   return `None` so the tool runs.
4. **Write `audit_hook` as a post-hook (`src/scoutbot/hooks.py`).** A factory `audit_hook(sink)` returns
   a post-hook that appends `{tool, args, observation}` to the given list — every call, blocked or not.
   It changes nothing; it only records.

### Part 2 — Wire it into the loop, and prove it (`loop.py`, `run_hooks.py`, `tests/`)

5. **Thread hooks through the loop (`src/scoutbot/loop.py`).** Give `run_agent_loop` optional `hooks`,
   `ledger`, and `subagent` parameters. Offer `issue_refund` in the tool list **only when a ledger is
   present**, and wrap the tool dispatch (`_execute_client_tool`) in `run_hooked` so every call runs
   through the pre/post seam. Keep the change additive — no existing behaviour moves.
6. **See it work offline (`run_hooks.py`).** With an in-memory ledger and a stubbed approver, drive
   `run_hooked` on `issue_refund` for four cases: a small refund that runs untouched; a large refund
   **blocked** when the approver says no; the same large refund **approved** and paid; and that approved
   refund issued **again**, kept to once by the ledger. Print the audit trail — all four calls, blocked
   ones included. **No Anthropic key needed.**
7. **Test the hooks offline (`tests/test_hooks.py`).** Cover `run_hooked` (no hooks; a pre-hook blocks
   and `execute` never runs; post-hooks fire on both outcomes); `refund_guard` (ignores other tools;
   blocks without approval; allows within policy); and `issue_refund` idempotency with
   `Ledger.in_memory()`. Add one loop-integration test: patch the client to request a refund and assert
   the guard blocks it, and that `issue_refund` is not offered without a ledger.

### Part 3 — The subagent, lightly (`subagent.py`) — read it; wire it if you have time

8. **Read `subagent.py` and its contract.** A `ResearchResult` (Pydantic: `answer`, `sources`,
   `confidence`) is the shape a research subagent returns. `ResearchSubagent.run(question)` retrieves
   passages and synthesises a validated result — the parent depends on the *shape*, never the steps, and
   off-contract output fails fast. `run_subagent.py` shows two questions answered as `ResearchResult`s.
9. **(If time) Wire `research_policy` into the loop.** Offer the tool only when a `subagent` is present,
   dispatch it to `subagent.run(...)`, and confirm an off-contract synthesis raises rather than slips
   through. Same habit as every day: bump the version, export the new names from `__init__.py`, commit,
   open a PR.

> **One gotcha worth naming.** The guard must key off the tool **name**. A `refund_guard` that inspects
> `args` without first checking `name == "issue_refund"` will try to read a `customer_id`/`amount` off a
> `search_policy` call and either crash or wrongly block a read. Guard the refund; wave everything else
> through.

## Expected outcome (minimum requirements)

- [ ] **A hook mechanism** — `run_hooked` runs pre-hooks (which can veto), calls the tool if none did,
  then runs post-hooks either way
- [ ] **A guarded refund** — `refund_guard` blocks a large refund without approval and allows it with
  approval, and ignores every non-refund tool
- [ ] **An idempotent tool** — `issue_refund` records to the ledger and a repeat call is a no-op; the
  guard and the ledger answer different questions
- [ ] **An audit post-hook** — `audit_hook` records every call, blocked ones included, and changes
  nothing
- [ ] **Wired into the loop** — `run_agent_loop` accepts `hooks`/`ledger`, offers `issue_refund` only
  with a ledger, and dispatches through `run_hooked`
- [ ] **`run_hooks.py`** shows the four-case refund arc and prints the audit trail, with no key
- [ ] **Offline tests (`tests/test_hooks.py`)** cover the mechanism, the guard, idempotency, and one
  loop-integration case
- [ ] **The whole earlier suite still passes** — hooks are additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Wire the subagent.** Offer `research_policy` when a `subagent` is present, dispatch it, and assert an
  off-contract synthesis fails validation instead of reaching the parent.
- **Make a hook rewrite args, not just veto.** A pre-hook can return a *modified* input (e.g. clamp a
  refund to the policy limit) rather than blocking outright. What changes in `run_hooked`?
- **Add a second post-hook** that records a metric (count of blocked vs allowed refunds) alongside the
  audit trail. Note that order matters and neither post-hook can change the result.
- **Guard a second tool.** `escalate_to_human` is safe, but imagine a `close_ticket` with an effect —
  what would its guard check, and would it need the ledger?

## If you're running out of time

Protect Part 1 and steps 5–7: the hook mechanism, the guarded and idempotent `issue_refund`, wired into
the loop, proven by `run_hooks.py` and `tests/test_hooks.py`. That is what the day is assessed on. **The
subagent (Part 3) is the first thing to cut** — it is there to read, and wiring it is optional. Do not
cut the ledger from `issue_refund` (a refund that can pay twice has missed the point) or fold the policy
into the tool (the guard must be a separate pre-hook). Flag whatever you skipped rather than quietly
leaving it out. (Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
