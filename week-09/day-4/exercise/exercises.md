# W9D4 Exercise — Let ScoutBot Decide How Hard to Look

## Scenario

Yesterday ScoutBot learned to search, judge, and search again — a real retrieval loop, bounded so it
always returns. But it runs that loop on **every** ticket. A customer writing "thanks, that's all I
needed!" gets a formulated query, a vector search, a critique, and possibly a reword — all to answer a
message that needs no policy at all. Meanwhile a crisp "how long do refunds take?" gets the same
heavyweight loop when one clean search would do.

Today you make retrieval **adaptive.** You add a **router** at the front: a node that classifies each
ticket into one of three strategies and sends it down a matching path. A thank-you skips retrieval
entirely. A clear policy question searches **once**. An oblique or account-specific question gets Day
3's **full loop.** Same loop underneath — you are deciding *whether and how much* to run it.

## Starting point

`scoutbot-baseline/` is **Day 3's finished agent**: it formulates a query, retrieves, critiques, and
rewords up to `MAX_RETRIEVAL_ATTEMPTS`. Everyone extends this same baseline, in place. Three things to
know:

- **The loop is done.** `formulate_query`, `critique_retrieval`, `route_after_critique` and the bounded
  back-edge all work. You are putting a fork *in front* of the loop, not rewriting it.
- **You are touching the graph again.** One new node, one new router, one new clause in an existing
  router, and one new field. The loop's internals do not move.
- **The safe default is `iterative`.** A router is a fallible model call; when it is unsure, it should
  search *harder*, never skip retrieval on a real question.

## Your task

Working in pairs, on a new branch:

### Part 1 — The routing model call (`schema.py` and `core.py`)

1. **Name the three strategies.** In `schema.py`, add a `QueryRoute(str, Enum)` with `direct`,
   `retrieve`, and `iterative`, next to `Category` and `Priority`. A `str` enum so the value stored in
   state is a plain string the checkpointer serialises.
2. **Write `classify_query`.** In `core.py`, add `classify_query(ticket_text) -> str`: one cheap
   `messages.create` (`max_tokens` in the low teens, no tool schema) with a `ROUTER_SYSTEM` prompt that
   describes the three strategies and asks for exactly one word back. Parse the reply to one of the
   three values, and **fall back to `iterative`** on anything unrecognisable — a router that fails
   should mean more retrieval, not a skipped search.

### Part 2 — The fork in the graph (`graph.py`), then a demo and tests

3. **Give the state a route.** Add one field to `TicketState`: `route: str` (last-write). Start it in
   `initial_state`.
4. **Write `classify_query_node`.** It calls `classify` (an **injected** parameter defaulting to
   `core.classify_query`, exactly like `formulate` and `kb`) and writes `route` plus a note naming the
   choice.
5. **Write `route_query`.** A plain function of state: return `"direct"`, `"retrieve"`, or
   `"iterative"` from `state["route"]`, falling back to `"iterative"` for anything missing or
   unexpected. This is the adaptive fork.
6. **Let a single-shot route skip the reword.** Add one clause to `route_after_critique`: if
   `state["route"]` is `"retrieve"`, return `"draft_reply"` even on a weak score. `iterative` keeps Day
   3's behaviour exactly. (Optional but tidy: have `critique_retrieval_node` read the route so a
   single-shot weak result's note says "drafting anyway" instead of promising a reword.)
7. **Wire the fork.** After `triage_ticket`, go to `classify_query`, then
   `add_conditional_edges("classify_query", route_query, {"direct": "draft_reply", "retrieve":
   "formulate_query", "iterative": "formulate_query"})`. Two routes share the loop's entry; `direct`
   jumps past it straight to `draft_reply`. Bind `classify` into the node with `functools.partial`, like
   `formulate`. **Keep the loop's back-edge the only cycle in the graph.**
8. **See it work.** Write `run_router.py` that runs three tickets — one per route — and prints the
   strategy the classifier chose and the retrieval path each took (no search for `direct`, one line for
   `retrieve`, the loop for `iterative`).
9. **Test it, offline.** Keep the graph offline by injecting a fake `classify` — patch the module
   global to a fake that returns `"iterative"` in your fixture (so every earlier test runs the same path
   and the call-count assertions still see only triage's model call), and pass fakes returning
   `"direct"` / `"retrieve"` for the routing tests. Assert: `classify_query_node` records the route;
   `route_query` covers its three exits and the safe fallback; `route_after_critique` lets a `retrieve`
   ticket skip the reword; and end to end, a `direct` ticket enters **none** of the loop's three nodes
   while a `retrieve` ticket searches exactly once.
10. **Same habit as every day**: commit on your branch, open a PR. Confirm the earlier tests still pass.

> **One trap worth naming.** If you leave `classify_query` calling the real model in your tests, it will
> hit your mocked Anthropic client, and your "the model was called once" assertions will start counting
> *two* calls (triage + classify). Inject the fake — the graph should never call a model to check its
> own routing. (This is the same gotcha Day 3's `formulate_query` had; the fix is the same.)

## Expected outcome (minimum requirements)

- [ ] **`QueryRoute` names the three strategies** (`direct`, `retrieve`, `iterative`), a `str` enum
- [ ] **`classify_query` returns one strategy** from a cheap model call and **falls back to `iterative`**
- [ ] **`TicketState` has `route`**, started in `initial_state`
- [ ] **`classify_query_node` takes `classify` as an injected parameter** and records the route
- [ ] **`route_query` covers its three exits** and falls back to `iterative` on anything unexpected
- [ ] **`route_after_critique` lets a `retrieve` ticket draft without rewording**; `iterative` unchanged
- [ ] **A `direct` ticket skips retrieval entirely** — no query, no search, no critique
- [ ] **The graph still has exactly one cycle**: `critique_retrieval -> formulate_query`
- [ ] **`run_router.py` shows all three routes** side by side
- [ ] **Offline tests** with an injected `iterative` fake in the fixture and `direct` / `retrieve` fakes
  for the routing cases
- [ ] Earlier tests still pass; work is on a branch with an open pull request

## If you finish early

- **Route off triage instead of a new call.** You already run `triage`, which classifies the ticket.
  Could its `category` (or a new field on the triage schema) pick the route, saving a model call? Try
  it, and note the trade-off: one fewer call, but the routing decision is now tangled into the triage
  prompt. Where would you rather own it?
- **Measure the routing.** Run twenty mixed tickets and log the route each got. How many `direct`s did
  you save a search on? Did any real question get routed `direct` (a false skip — the dangerous error)?
  That miss rate is the number a production router lives or dies on.
- **Add a confidence gate.** Have `classify_query` return not just a route but how sure it is, and route
  low-confidence classifications to `iterative` regardless. You are building the "when unsure, search
  harder" default into the classifier itself.
- **A fourth route.** Some tickets are *account-specific* ("why was **my** last order refunded?") —
  policy alone will not answer them. Sketch (don't fully build) where a `memory` route would go. That is
  Friday, and this is the seam it plugs into.

## If you're running out of time

Protect steps 4, 5, 6, and 7: the classify node, the router, the single-shot clause, and the wiring
that forks on the route. That fork — classify, then retrieve as hard as the ticket deserves — is what
the day is assessed on. Trim the tests (step 9) to two cases first (`route_query`'s three exits; one
end-to-end `direct` ticket that skips the loop), then `run_router.py`'s third ticket (step 8 — keep at
least the `direct` and `retrieve` ones so the contrast is visible). Do **not** drop the `iterative`
fallback: a router with no safe default sends an unrecognised classification down whatever path it
happens to land on, which on a real question means a skipped search and a guessed answer. Flag whatever
you skipped rather than quietly leaving it out. (Coaches: see the coaches' page "Contingency plans" for
exactly what to prioritise.)
