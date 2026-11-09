# ScoutBot Cost, Latency & Planning Decision Guide

Day 1's guide was about *topology* — which multi-agent shape fits. Today's is about the two levers you
pull once the shape exists: **how the team decides what to do** (planning) and **what that decision
costs** (cost/latency). As before, the skill is naming the problem precisely; the pattern is then a
lookup.

## Planning: how does the team pick who works?

| When the ticket… | Reach for | Why | Built |
| --- | --- | --- | --- |
| names one obvious kind of work | a **keyword dispatcher** (`classify_specialty`) | cheapest possible, no key, readable and testable — good enough for the clear cases | Day 1 |
| is ambiguous or worded obliquely | a **model classifier** (inject `classify`) | "how long do refunds take?" is a *policy* question, not a refund — the model reads intent the keywords miss | Day 1 (named) → today |
| needs **several** specialists in order | a **model planner** (`plan_ticket` → an ordered `plan`) | one classification is not enough; the plan is the ordered list the supervisor executes | **today** |
| might fail and need a different specialist | plan-and-execute with **re-planning** | watch a worker come back empty, loop to the planner, try again | capstone (named, not built) |

**The one-line upgrade path:** keyword rule → model classifier → model planner. Each is a strictly
smarter dispatcher feeding the *same* graph. Today takes the last step: the planner's ordered output is
exactly the `plan` Day 1's `supervisor_node` already loops over.

## Cost & latency: what does the decision cost, and how do you cut it?

| When you need… | Reach for | Why |
| --- | --- | --- |
| to know what a call cost | `cost_of(response.usage, model)` | every reply already reports its tokens; cost is `tokens x price`, no new tooling |
| to know what a *run* cost | a **`Meter`** threaded through the run | one `CallRecord` per call → a per-run total and a breakdown you can read after the fact |
| to know how slow a call was | `measure()` around it | `perf_counter` wall time — the honest latency from the caller's side |
| to cut the bill | **model tiering** (`pick_model`) | model choice is the single biggest lever; spend the strong tier only where difficulty earns it |
| to cut it further | **prompt caching** (rates are in `PRICING`) | a cached input token is ~10x cheaper; cache the long, stable system prompt (a later lever, not built) |

## Two decisions that look alike but aren't

- **"Which specialist?" vs "how hard is this?"** Routing picks *who* does the work; difficulty picks
  *which model* does it. A ticket can route to the refund worker (a `specialty`) and still be *easy*
  (plan on Haiku). `route_to_specialist` and `assess_difficulty` answer different questions — don't
  collapse them into one.
- **A stale price vs a missing price.** A price that drifted (Sonnet used to be $3/$15) makes your
  report quietly *wrong*; a model with no entry makes `cost_of` *crash* (`UnknownModelError`). The crash
  is the kinder failure — it is loud. Keep `PRICING` dated and add models deliberately.

## The transferable rule

**Measure before you optimize, and tier before you rewrite.** You cannot manage a bill you cannot see, so
the first move is always to read `usage` and price it. Once you can see it, the cheapest large win is
almost never a cleverer prompt or a new framework — it is sending the routine, high-volume work to a
cheaper model and reserving the expensive one for the tickets that actually need it.
