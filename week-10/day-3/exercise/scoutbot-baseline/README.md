# ScoutBot — Week 10 Day 3 Starting Point

This is where today starts: **your finished Week 10 Day 2 agent — now an MCP client *and* an MCP
server.** Over the first two days ScoutBot learned both sides of the Model Context Protocol: Monday it
*called* a tool another team published; Tuesday it *published* two of its own (`search_policy`,
`look_up_customer`) so any client can reach them. Both days added **reach** — more tools, more callers.

Today adds **restraint.** ScoutBot gets its first tool with a real-world effect — `issue_refund`, which
moves money — and the day is about what should stand between the model and that effect. You will build
two seams around every tool call: a **pre-hook** that can veto a call before it runs, and a **post-hook**
that witnesses it after. Then, in the same spirit, you will look at a **subagent**: an agent you call
like a tool, that answers a scoped question and hands back a checked contract instead of raw steps.

> **Today is a Career Session day.** The technical block is deliberately short — one topic, three
> concepts, a ~25-minute hands-on — to leave room for the Career Session that runs alongside it.

What you have:

- `src/scoutbot/loop.py`, `core.py`, `graph.py` — the agent, with the tool-dispatch point
  (`_execute_client_tool`) you will wrap with hooks today. Untouched otherwise.
- `src/scoutbot/tools.py` — the native tools (`look_up_customer`, `escalate_to_human`, …), each with a
  hand-written schema. Today you add `issue_refund` here.
- `src/scoutbot/notify.py` — **the `Ledger` from Week 8 Day 4.** A send-once record keyed by a stable
  string; you will reuse it to make `issue_refund` idempotent.
- `src/scoutbot/policy.py` — **the refund rules from Week 8 Day 4** (amount limit, plan, recent-refund
  count, who must approve). Your guard will consult these; you do not rewrite them.
- `src/scoutbot/knowledge.py` — the `KnowledgeBase` with a `search()` method a research subagent would
  call.
- `src/scoutbot/mcp_client.py`, `mcp_server.py` — Days 1–2, untouched today.
- `tests/` — the full suite, all passing. Today's tests add hook and subagent files that stay offline
  with an injected approver, an in-memory ledger, and a stub knowledge base.

## Three things worth knowing before you start

**1. A hook is a plain callable, not a framework.** A pre-hook has the shape `(name, args) ->
Optional[dict]`: return a dict to **block** the call (that dict becomes the observation), or `None` to
let it run. A post-hook has the shape `(name, args, observation) -> None`: it only **watches**. A small
`run_hooked(name, args, execute, hooks)` runs the pre-hooks, calls `execute` if none vetoed, then runs
the post-hooks either way. That is the whole mechanism.

**2. Keep the guard and the tool separate.** The guard (`refund_guard`, a pre-hook) owns *policy*: it
reads the customer, applies the Week 8 refund rules, and asks a human approver for anything at or above
the limit. The tool (`issue_refund`) owns the *effect* and its *idempotency* (keyed through the ledger).
"Should this run?" and "has this already run?" are different questions with different answers — the
guard decides the first, the ledger the second.

**3. Everything stays offline.** Inject the approver (`approve_fn`) so tests pass a lambda instead of a
person; use an in-memory ledger; inject the subagent's knowledge base and synthesis. Same
"mock-the-collaborator" discipline every prior week used.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — only the reasoning-loop demos need it; run_hooks.py does not
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

No new dependency today: everything you need (`mcp[cli]`, the ledger, the policy) is already here.

## Run

```bash
uv run python run_mcp_server.py   # Week 10 Day 2: a client calls ScoutBot's own tools, served over MCP
uv run python run_mcp.py          # Week 10 Day 1: the model calls an order-status tool served over MCP
uv run python run_memory.py       # Week 9 Day 5: the same customer twice, the second recalls the first
uv run python run_router.py       # Week 9 Day 4: classify the ticket, then retrieve as hard as it deserves
uv run python run_rag.py          # Week 9 Day 2: retrieve once, draft a grounded, cited reply
uv run python main.py             # Week 7's loop, unchanged
uv run pytest                     # the full suite, passing, before you change anything
```
