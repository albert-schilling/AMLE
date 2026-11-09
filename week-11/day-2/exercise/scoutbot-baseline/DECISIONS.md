# ScoutBot Integration Decision Guide

The transferable idea of Week 10, in one table: **match the problem to the pattern.** Each row is a kind of
problem an agent faces and the pattern that solves it. The skill is naming the *problem* precisely — the
pattern is then almost a lookup.

| When you need… | Reach for | Why | Built |
| --- | --- | --- | --- |
| a tool you didn't write | an **MCP client** (`MCPToolProvider`) | the capability lives in another program; call it over the protocol instead of reimplementing it | Day 1 |
| to publish a capability to others | an **MCP server** (`build_server`) | expose your tools with typed schemas so any client can discover and call them | Day 2 |
| a call that must not run unless allowed | a **pre-tool-use guard** (`refund_guard`) | authorisation belongs in a code path every call passes through, not in the prompt the model can talk around | Day 3 |
| a side effect that must run at most once | an **idempotent ledger** (`Ledger` + a stable key) | a request-derived key makes a retried or repeated call a no-op, so money moves once | Week 8 |
| a validated final answer | a **typed `output_type`** (Pydantic AI) | the framework derives the schema, validates the reply, and retries — you write the contract, not the loop | Day 4 |
| a rule the type cannot express | an **output validator** (`ModelRetry`) | types check the *form*; a validator checks the *meaning*, re-prompting on a miss | Day 4 |
| a scoped side-question answered | a **subagent** (`ResearchSubagent`) | delegate a self-contained question and get a contracted result back, without derailing the main loop | Day 3 |
| to see what happened | an **audit post-hook + a trace** (`audit_hook`, `log_step`) | witness every call (blocked or not) and record every step, so a run can be read back later | Day 3 / Wk 8 |
| to classify, then act | **classify-then-resolve** (`resolve_ticket`) | a real ticket handler decides *what kind* of request this is (a contract) and then *resolves* it (a tool loop) | Day 5 |

## Two problems that look alike but aren't

- **"Not allowed" vs "not twice."** A refund needs *both* a guard (authorisation: is this refund permitted?)
  and a ledger (idempotency: has this exact refund already fired?). They are different problems with
  different patterns; Day 3 used both on the one `issue_refund` tool. Naming which you mean is the whole
  skill.
- **A type vs a validator.** A type rejects `priority="urgent!!"` (wrong shape). A validator rejects
  `suggested_owner="the billing people, probably"` (right shape, wrong meaning). Reach for the type first;
  add a validator only for the rules the type cannot say.

## Patterns compose

One ticket often needs several at once. `resolve_ticket` shows it: a **typed contract** classifies, then the
loop resolves under a **guard** and an **audit**, moving money through an **idempotent ledger**, calling an
**MCP tool** it did not write, and able to **delegate** a policy question — all recorded to a **trace**. The
guide is not "pick one"; it is "name each problem, reach for each pattern, and wire them together."

## One row of our own (a problem ScoutBot does not yet solve)

| When you need… | Reach for | Why |
| --- | --- | --- |
| many agents to cooperate on one task | an **orchestrator/supervisor** (Week 11) | when a task needs several specialists in a defined flow, one loop is not enough — you coordinate agents, not just tools |

That is next week. Today's stack is one agent, fully composed; Week 11 is many.
