# W11D2 Exercise — Give the Team a Brain and a Budget

## Scenario

Yesterday you split ScoutBot into a team. Today Priya has two complaints. First, the dispatcher is dumb:
*"how long do refunds take?"* keeps landing on the refund worker when it is a policy question, and a
ticket that needs *two* specialists ("check the policy, then refund me") can't be expressed at all — the
supervisor's `plan` is typed in by hand. Second, finance has noticed the model bill and nobody can say
what a ticket costs or why.

So today you give the team **a brain and a budget**. You build a **model-backed planner** that turns a
ticket into the ordered list of specialists to consult — the `plan` your Day 1 supervisor already runs —
and you build a thin **cost/latency metering** layer that reads what every model call already reports, so
you can see the bill and cut it with **model tiering**.

## Starting point

`scoutbot-baseline/` is **the finished Day 1 team** — orchestrator, supervisor, and the three worker
subgraphs, all passing. Everyone extends this same baseline, in place. Three things to know:

- **The planner is a smarter dispatcher.** Day 1's `classify_specialty` returned one specialty from
  keywords; your planner returns an *ordered list* from the model. Same job, one rung up.
- **It feeds the supervisor you already built.** `supervisor_node` loops over a `plan` list. Your planner
  writes that `plan`, so the planner slots in *front of* the supervisor — you are not rebuilding the team.
- **Cost is `tokens x price`.** Every reply carries `response.usage` (`input_tokens`, `output_tokens`,
  and two cache counters). No new dependency: price it against a small table, time it with
  `time.perf_counter()`.

## Your task

Working in pairs, on a new branch. **No new dependency today** — planning is one more model call through
the SDK you already have; cost is arithmetic.

### Part 1 — Cost & latency metering (`src/scoutbot/metering.py`)

1. **A dated price table.** `PRICING`: per-million-token input/output (and cache) rates for at least
   `claude-haiku-4-5` and `claude-sonnet-5`. **Confirm today's prices** on the Anthropic pricing page and
   date the table in a comment — they drift.
2. **`cost_of(usage, model) -> float`.** Read the token counts off `response.usage` and price each at its
   rate. Treat the cache counters as 0 when `None`. **Raise** on a model with no price rather than
   returning a misleading `$0.00`.
3. **A `Meter`.** An accumulator with a `record(label, model, usage, latency_ms)` that appends one
   `CallRecord`, plus `total_cost` / `total_tokens` and a printable `report()`.
4. **`measure()`** — a context manager timing its block with `perf_counter`, so a call reads
   `with measure() as sw: resp = ...` and `sw.ms` is the wall time.
5. **Model tiering.** `TIERS` (cheap/strong) and `pick_model(difficulty) -> str` — `hard` gets the strong
   tier, everything else the cheap one (cheap is the safe default).

### Part 2 — The model-backed planner (`src/scoutbot/planner.py`)

6. **A `make_plan` tool + a system prompt.** A one-tool schema whose `steps` is an ordered array of the
   three specialty names; a system prompt that explains the three specialists and asks for the ordered
   list (most tickets need exactly one).
7. **`plan_ticket(ticket_text, *, model=None, meter=None) -> list[str]`.** One `messages.create` call with
   `tool_choice` forcing `make_plan`, wrapped in `measure()`, going through an injectable/patchable
   `_client` (the same seam as `core.triage`). Parse the tool call into an ordered list of *valid*
   specialties, falling back to `["research"]`. If a `meter` is passed, record the call under `"plan"`.
8. **Tier by difficulty.** With no `model` argument, pick the model via
   `pick_model(assess_difficulty(ticket_text))` — write a cheap, deterministic `assess_difficulty`
   heuristic (multi-intent / long / explicitly sequenced → `hard`).
9. **`planner_node`** — a graph node that writes `plan` and one `transcript` step, with an injectable
   `make_plan` (default `plan_ticket`) so a test drives it with a one-line stub.
10. **`build_planning_team(...)`** — Day 1's `build_supervisor` with `planner` inserted:
    `START -> look_up_customer -> planner -> supervisor <-> workers -> END`. Reuse `build_workers`,
    `supervisor_node` and `look_up_customer_node` from `orchestrator` unchanged.

### Part 3 — Demos and offline tests

11. **See the cost lever (`run_cost.py`), no key.** From a few *recorded* `Usage` numbers, print the
    per-call cost report, a Haiku-vs-Sonnet comparison, and a volume projection (`x N tickets/day`).
12. **See it plan (`run_planner.py`), needs a key.** Run `build_planning_team(meter=...)` over a one-step
    ticket, a two-step ticket, and a three-step one; print each plan, the transcript, and the `Meter`
    report.
13. **Test metering (`tests/test_metering.py`), offline.** `cost_of` (base tokens, cache reads, the
    unpriced-model raise), `pick_model` both ways, the `Meter` totals, and `measure()` over a small sleep.
14. **Test the planner (`tests/test_planner.py`), offline.** `_parse_plan` (order kept, unknowns dropped,
    empty → `["research"]`); `plan_ticket` through the **patched `_client`** (returns the plan, records on
    the meter, tiers by difficulty); `planner_node` with an injected stub; and the **whole planning team
    end to end** with a stub `make_plan`, proving the planner feeds the supervisor and both specialists run.
15. **Same habit as every day**: keep the whole suite green, commit on your branch, open a PR.

> **One gotcha worth naming.** Do *not* spend a model call inside `assess_difficulty` to decide whether to
> spend a model call — that defeats the point. Keep it a cheap heuristic. And thread *one* `Meter` through
> a run rather than creating a new one per call, or your totals reset.

## Expected outcome (minimum requirements)

- [ ] **`cost_of` reads `response.usage`** and raises on an unpriced model (no silent `$0.00`)
- [ ] **A `Meter`** that accumulates per-call cost/latency and reports a run total
- [ ] **Model tiering** (`pick_model`) with cheap as the safe default
- [ ] **`plan_ticket`** returns an ordered list of valid specialties via one `make_plan` tool call, with a
  `["research"]` fallback, through a **patched-`_client`** seam
- [ ] **The planner tiers by difficulty** — a one-liner plans on the cheap model, a multi-part ticket on
  the strong one
- [ ] **`build_planning_team`** = Day 1's supervisor with the planner in front (reusing the workers unchanged)
- [ ] **`run_cost.py`** shows the tiering comparison with **no key**; **`run_planner.py`** runs the metered team
- [ ] **Offline tests**: metering values, `_parse_plan`, `plan_ticket` (patched), `planner_node` (stub),
  and the whole planning team end to end
- [ ] **The Day 1 + Week 10 suite still passes** — the day is additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Prove the mis-route is fixed.** Find the ticket the keyword rule got wrong (*"how long do refunds
  take?"* → refund) and show the planner routes it to `research`. What did you pay (a key, latency, cost)
  to get that?
- **Meter a whole run, not just the plan.** If you wired a model-backed draft anywhere, record it on the
  same `Meter` and read the breakdown — where did the money actually go?
- **Tune the tier threshold.** Feed `assess_difficulty` ten real tickets. Does it over- or under-escalate?
  Adjust the heuristic and justify the trade (a wrong "easy" is a weaker plan; a wrong "hard" is wasted money).
- **Cache the system prompt.** The planner's system prompt is long and identical every call. Read the
  cache rates already in `PRICING` and estimate the saving if it were cached. (Turning caching on is a
  later lever — estimate it first.)

## If you're running out of time

Protect Part 1 (metering: `cost_of`, `Meter`, `pick_model`) and steps 6–7 and 9 (the planner call and
node), then step 14's `plan_ticket` and end-to-end team tests. That core — *a model plans an ordered list
of specialists, it's metered, and the supervisor runs it, all proven offline* — is what the day is
assessed on. The difficulty-tiering (step 8) and `run_planner.py` (needs a key) are the first things to
trim; `run_cost.py` stays because it needs no key. **Do not** skip the `cost_of` raise on an unpriced
model or the `["research"]` planner fallback — a silent `$0.00` and an empty plan are the two quiet bugs
that mislead everyone downstream. Flag whatever you skipped rather than leaving it silently out. (Coaches:
see the coaches' page "Contingency plans".)
