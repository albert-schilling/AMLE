# W9D3 Exercise — Let ScoutBot Search, Judge, and Search Again

## Scenario

Yesterday ScoutBot started answering from the source: it retrieved the passages that matched a ticket
and grounded its reply in them. But it retrieved **once**, on the raw ticket text — a customer venting
("this is the third time I've asked!"), not a search query. When that text happens to be a bad query,
retrieval comes back weak, and the bot's only move is to draft a thin answer or decline. It never stops
to think *"that search didn't work — let me try a different one."*

Today you give it that move. You will turn retrieval into a **loop the agent drives**: a node that asks
the model to **formulate a search query** from the ticket, a node that **critiques** what came back, and
a **back-edge** that rewords the query and searches again when the result is weak — bounded, so it
cannot loop forever. By the end, a badly-worded ticket that missed on the first search gets a second,
better query and a grounded answer, and a genuinely-uncovered question rewords a couple of times, gives
up honestly, and declines.

## Starting point

`scoutbot-baseline/` is **Day 2's finished agent**: it retrieves once and drafts a grounded, cited
reply. Everyone extends this same baseline, in place. Three things to know:

- **Grounding is done.** `stream_reply(..., knowledge=...)`, `format_passages`, `LOW_CONFIDENCE` and the
  `retrieve_knowledge` node all work. You are wrapping them in a loop, not rewriting them.
- **You are touching the graph again today.** Two new nodes, one changed node, one new router, and a
  cycle. The nodes downstream of drafting do not move.
- **The bound is the point.** A loop that can reword forever is a bug, not a feature. `MAX_RETRIEVAL_
  ATTEMPTS` is what makes self-correction safe.

## Your task

Working in pairs, on a new branch:

### Part 1 — The query-writing model call (`core.py` and one constant in `knowledge.py`)

1. **Bound the loop.** In `knowledge.py`, add `MAX_RETRIEVAL_ATTEMPTS` (start at `3`) next to
   `LOW_CONFIDENCE`. The two constants are the loop's whole policy: one score triggers a retry, one
   count stops it. A named constant, not a `3` buried in a router.
2. **Write `formulate_query`.** In `core.py`, add `formulate_query(ticket_text, tried_queries=(),
   weak_passages="")` that returns a short search query — a handful of keywords naming the policy topic,
   no punctuation. It has **two moods**: with no `tried_queries` it writes an opening query from the
   ticket (a `QUERY_SYSTEM` prompt); with tried queries it is told what already failed and asked to
   **reword** (a `REQUERY_SYSTEM` prompt — "try a synonym, a broader term, the specific policy area").
   Fall back to the ticket text if the model returns nothing usable.

### Part 2 — The loop in the graph (`graph.py`), then a demo and tests

3. **Give the state room for the loop.** Add three fields to `TicketState`: `search_query: str`
   (last-write), `tried_queries: Annotated[list[str], operator.add]` (accumulates — so the attempt bound
   is just its length), and `retrieval_ok: bool` (the critique's verdict). Start all three in
   `initial_state`.
4. **Write `formulate_query_node`.** It calls `formulate` (an **injected** parameter defaulting to
   `core.formulate_query`, exactly like `kb` and `ledger`) and writes `search_query` and appends to
   `tried_queries`. On a reword pass it passes the tried queries and the current weak passages
   (`format_passages(state["retrieved"])`) to `formulate`, so the model knows what to move away from.
5. **Retrieve the chosen query.** Change `retrieve_knowledge_node` to search `state["search_query"]`
   (falling back to the ticket text), overwriting the previous attempt's passages.
6. **Write `critique_retrieval_node`.** A **cheap, deterministic** gate: set `retrieval_ok = best score
   >= LOW_CONFIDENCE`. Keep it free — the expensive step is the reword, so the check that decides
   whether to spend a model call must not itself be one. Add a note; when the loop is out of tries
   (`len(tried_queries) >= MAX_RETRIEVAL_ATTEMPTS`) say it is drafting a decline.
7. **Write `route_after_critique`.** Return `"draft_reply"` if `retrieval_ok`, `"draft_reply"` if the
   attempts are spent, else `"reformulate"`. This is the whole control flow.
8. **Wire the cycle.** Replace Day 2's single edge into `retrieve_knowledge` with:
   `triage_ticket -> formulate_query -> retrieve_knowledge -> critique_retrieval`, then
   `add_conditional_edges("critique_retrieval", route_after_critique, {"reformulate": "formulate_query",
   "draft_reply": "draft_reply"})`. Bind `formulate` into `formulate_query_node` with
   `functools.partial`, like `kb`. That back-edge to `formulate_query` is the only cycle in the graph.
9. **See it work.** Write `run_agentic.py` that runs a couple of tickets and prints **one line per pass
   through the loop** — the query, the best score, the verdict — including one question the corpus does
   not cover, so you can watch it reword, hit the bound, and decline.
10. **Test it, offline.** Keep the graph offline by injecting a fake `formulate` — patch the module
    global to an **echo** fake in your fixture (so call-count assertions still see only triage's model
    call), and pass a **scripted** fake (a different query per attempt) to drive the reword path in the
    loop tests. Assert: `formulate_query_node` records the query and rewords using tried/weak on the
    second pass; the critique passes a strong score and flags a weak one; the router covers its three
    exits; and end to end, a weak-then-strong script rewords once and succeeds while an always-weak
    script stops at `MAX_RETRIEVAL_ATTEMPTS`.
11. **Same habit as every day**: commit on your branch, open a PR. Confirm the earlier tests still pass.

> **One trap worth naming.** If you leave `formulate_query` calling the real model in your tests, it
> will hit your mocked Anthropic client, and your "the model was called once" assertions will start
> counting *two* calls (triage + formulate). Inject the fake — the graph should never call a model to
> check its own wiring.

## Expected outcome (minimum requirements)

- [ ] **`MAX_RETRIEVAL_ATTEMPTS` is a named constant** bounding the loop
- [ ] **`formulate_query` writes a query and rewords** when told what already failed (two system prompts)
- [ ] **`TicketState` has `search_query`, `tried_queries` (a reducer) and `retrieval_ok`**, started in
  `initial_state`
- [ ] **`formulate_query_node` takes `formulate` as an injected parameter** and records the query
- [ ] **`retrieve_knowledge_node` searches `search_query`**, not the raw ticket
- [ ] **`critique_retrieval_node` is score-only and deterministic**, and knows when the attempts are spent
- [ ] **`route_after_critique` loops back on a weak result and moves on otherwise**, bounded by the limit
- [ ] **The graph has exactly one cycle**: `critique_retrieval -> formulate_query` on `"reformulate"`
- [ ] **`run_agentic.py` shows the loop** — a reword-then-hit and a bounded give-up
- [ ] **Offline tests** with an echo fake in the fixture and a scripted fake for the loop cases
- [ ] Earlier tests still pass; work is on a branch with an open pull request

## If you finish early

- **Make the critique smarter.** Right now it trusts the cosine score. Add a *model* critique: hand the
  query and the top passage to the model and ask "does this actually answer the ticket? yes/no." Where
  does it catch a miss the score waved through, and what does the extra model call cost you per ticket?
- **Show the reword earning its keep.** Find a ticket whose raw text is a bad query but whose *topic* is
  covered. Log the first (failing) query and the reworded (succeeding) one side by side. That delta —
  bad search to good search, no change to the corpus — is the whole value of making retrieval agentic.
- **Vary the bound and measure.** Set `MAX_RETRIEVAL_ATTEMPTS` to `1` (back to Day 2) and to `5`. On a
  handful of hard tickets, how often does a second or third try actually rescue an answer, and where is
  it just three searches to reach the same decline? You are pricing self-correction.
- **Dedupe the rewords.** Nothing stops the model returning a query it already tried. Detect a repeat in
  `formulate_query_node` and either nudge the prompt harder or short-circuit to the decline. A loop that
  reasks the same question is a bound spent for nothing.

## If you're running out of time

Protect steps 4, 6, 7, and 8: the formulate node, the critique, the router, and the wiring that makes
them a cycle. That loop — search, judge, reword, search again, stop at the bound — is what the day is
assessed on. Trim the tests (step 10) to two cases first (the router's three exits; one end-to-end
weak-then-strong reword), then `run_agentic.py`'s second ticket (step 9 — keep at least the
reword-then-hit one). Do **not** drop the bound: an agentic loop with no `MAX_RETRIEVAL_ATTEMPTS` is the
one change today that turns a self-correcting bot into one that can spin forever on an unanswerable
question. Flag whatever you skipped rather than quietly leaving it out. (Coaches: see the coaches' page
"Contingency plans" for exactly what to prioritise.)
