# ScoutBot — Week 11 Day 4 Starting Point

This is where today starts: **the finished Day 3 team, now with an eval.** ScoutBot plans, routes to
specialist workers, meters its own cost, and — as of yesterday — can be **graded**: a labelled `EVAL_SET`
scored by deterministic metrics and an optional LLM-as-judge turns "is it any good?" into a pass rate you
can rerun.

It does a lot. Today is the first day about what it should **not** do — and the honest lesson underneath
it is that **no single check is enough:**

> A prompt-injection can talk the model into ignoring its instructions. A customer can paste a credit-card
> number straight into a ticket. A single filter that tries to catch either one **will** be bypassed.

So today is about **defense-in-depth**: four independent layers, arranged so that when one misses, the next
still contains the damage. Only **one** of them is new.

```
L1  input guard      (NEW today)   scrub the ticket before the model reads it
L2  tool authZ       (Week 10 D3)  a tool must not run unless policy allows it   -> refund_guard
L3  output validation(Week 10 D4)  a malformed/unsafe result fails the contract -> TicketTriage
L4  human gate       (Week 8)      a person signs off high-risk actions          -> approve_fn / escalation
```

You build **L1** (`guard.py`) and then **compose** it with L2–L4, which you already built in earlier
weeks and which are all sitting in this baseline.

## What you have

- `src/scoutbot/hooks.py` — **L2**. `refund_guard` is a pre-tool-use hook: a refund over the policy limit
  does not run unless a human approves it, and the model cannot route around a code path. `run_hooked`
  wraps every client tool call.
- `src/scoutbot/typed_agent.py` + `src/scoutbot/schema.py` — **L3**. `TicketTriage` is the output contract;
  a value outside its enums fails validation loudly instead of becoming whatever the model wrote.
- `src/scoutbot/policy.py` — **L4**. `decide_approval` is the reviewable rule table; the loop's `approve_fn`
  is the human gate a high-risk action passes through.
- `src/scoutbot/loop.py` — the agent loop that already accepts `hooks` and `approve_fn`, so L2 and L4 wire
  in without touching control flow. Your L1 sits in *front* of it.
- `src/scoutbot/core.py` / `judge.py` — the `_client` seam every model call is faked through in tests. Your
  optional LLM-backed detector uses the same seam.
- `src/scoutbot/metering.py` — Day 2's `Meter`. If you add the LLM detector, you meter it like any other call.

## Three things worth knowing before you start

**1. L1 is brittle on purpose — that's the lesson, not a bug.** A regex injection filter you can enumerate
is one an attacker can paraphrase past. Do not try to make it airtight; make it one layer, and let L2–L4
catch what it misses. Your demo should *show* a bypass slipping through L1 and getting stopped downstream.

**2. You are composing, not rebuilding.** L2, L3, and L4 already work and are tested. Today adds one module
(the input guard) and shows the four layers standing in a row. Every prior test must still pass.

**3. Everything stays offline.** The input guard is pure regex + string work — no key, no network. The
optional LLM detector needs a key for a real call, but is faked through the patched `_client` seam in tests,
exactly like the judge.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — only the optional LLM-detector demo needs it
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

**No new dependency today.** deepeval arrived Wednesday and is already here; today's input guard is plain
Python. That is part of the point: a serious safety layer need not be a heavy dependency.

## Run

```bash
uv run python run_evals.py          # yesterday's eval, fully offline (the number you protect from regressions)
uv run python run_orchestrator.py   # the team, three tickets routed to three specialists (no key)
uv run pytest                       # the whole Week 8-11 suite, green, before you change anything
```
