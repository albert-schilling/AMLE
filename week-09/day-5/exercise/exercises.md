# W9D5 Exercise — Give ScoutBot a Memory of the Customer

## Scenario

All week ScoutBot got better at answering a *ticket*: it retrieves, grounds, loops, and now routes. But
every run still starts from nothing. A customer who wrote in an hour ago is a stranger now — the
checkpointer remembers a *run*, and nothing remembers a *person*. So the same customer, on their third
message about the same late refund, gets greeted as if it were the first.

Today you give ScoutBot a **cross-ticket, per-customer memory.** When a ticket finishes, ScoutBot
writes a short line about it, keyed to that customer. When the *next* ticket from that customer arrives,
ScoutBot recalls the relevant past lines **before** it drafts, and writes with them as background.

The trick is that you already built the hard part on **Day 1.** Memory is the knowledge base pointed at
a different question. Knowledge is one shared corpus, retrieved and **cited** — *"what does our policy
say?"*. Memory is many small, per-customer records, recalled as background and **never cited** — *"what
do we already know about this person?"*. Same embedder, same vectors-in-SQLite, same cosine ranking.
The only real differences are **scope** (a `customer_id` column that recall filters on) and **writing
once** (idempotent on `ticket_id`, the send-ledger's discipline again).

## Starting point

`scoutbot-baseline/` is **Day 4's finished agent**: the routed, pausing, retrying, ledgered, traced
graph that grounds, cites, and runs a bounded retrieval loop as hard as each ticket deserves. Everyone
extends this same baseline, in place. Three things to know:

- **You already own the machinery.** `knowledge.py` has the embedder, the `float32`-in-SQLite BLOB
  helpers (`_to_blob`/`_from_blob`), and `cosine_scores`. Your memory store reuses them — import, don't
  reinvent.
- **Memory brackets the graph, it does not thread through it.** One node near the front (recall), one
  node at the very end (write), one new state field. You do **not** touch the retrieval loop or the
  approval branch.
- **Memory is background, not a source.** It rides into the draft prompt as *"what you already know
  about this customer, use for context, do not cite"* — separate from the cited policy passages. Keep
  the two blocks distinct.

## Your task

Working in pairs, on a new branch:

### Part 1 — The memory store (`memory.py`)

1. **Build `MemoryStore`, reusing Day 1's parts.** New module `memory.py`. It takes an injected `embed`
   function (the same `EmbedFn` type the knowledge base uses) and opens a SQLite connection with
   `check_same_thread=False`. One table: `memories(customer_id, ticket_id, text, vec, ts)`, where `vec`
   is a `float32` BLOB. Reuse `_to_blob`/`_from_blob` and `cosine_scores` from `knowledge.py`.
2. **`write(customer_id, ticket_id, text) -> bool`, idempotent on `ticket_id`.** If this customer
   already has a memory for this ticket, write nothing and return `False`; otherwise embed the text
   **once** (on write, not on recall), insert, and return `True`. This is the send-ledger's "act once"
   applied to remembering — the write node runs at the end of a graph that can be resumed or re-run, and
   a store that grew a duplicate every replay would poison recall.
3. **`recall(customer_id, query, k=3, min_score=...) -> list[...]`.** Load **only this customer's** rows
   (`WHERE customer_id = ?` — that where-clause is the whole privacy property), score them against the
   embedded query with cosine, return the top `k` best-first, and **drop anything below `min_score`.**
   A customer with no history, or none relevant, gets an empty list — the normal first-contact case, not
   an error.
4. **Set the relevance floor *below* retrieval's, on purpose.** Define a `MEMORY_RELEVANCE` threshold
   lower than `knowledge.LOW_CONFIDENCE`. Be ready to justify it: a weak *retrieval* grounds a factual
   reply, so it errs toward silence with a high floor; a weak *recall* only adds reviewed background, so
   it errs toward remembering with a low one.
5. **Add `format_memories(...)`.** Render recalled memories as background lines — something like
   `- (ticket T-1001) asked about a late refund` — tagged with the ticket for tracing but with **no
   `[source]`** tag. It must **not** look like `format_passages`: a memory dressed as a citation is
   exactly the confusion to avoid. Accept both your recall objects and plain dicts (the graph keeps
   dicts in state).
6. **Test the store offline, first.** Inject a tiny keyword embedder (steal the one from
   `tests/test_knowledge.py`) and assert: write returns `True` then `False` on a repeat; recall returns
   only the queried customer's rows; recall ranks the relevant memory first and drops the sub-floor one;
   an unknown customer recalls `[]`; and a file-backed store recalls after being reopened. No model, no
   network.

### Part 2 — Two nodes and one argument (`graph.py`, `core.py`), then a demo

7. **Give the state a place for recall.** Add one field to `TicketState`: `recalled: list[dict]`
   (last-write is fine). Start it empty in `initial_state`.
8. **Write `recall_memory_node`.** It takes an **injected** `store` (defaulting to a lazy process-wide
   `MemoryStore`, exactly like `kb`/`formulate`/`classify` default to theirs), recalls this customer's
   memories for the ticket text, and writes them into `recalled` plus a note. Wire it in **right after
   `look_up_customer`**, so every route — even `direct` — has memory available before it drafts.
9. **Write `write_memory_node`.** It composes one short line about the finished ticket (the text, its
   triage category, and how it resolved), calls `store.write(...)`, and notes whether it wrote or found
   it already there. Wire it in **right after `send_reply`**, so a ticket is remembered only once it is
   truly done. Keep `critique_retrieval -> formulate_query` the **only cycle** in the graph.
10. **Feed recall into the draft, as background.** Give `core.stream_reply` a new `memory` argument and
    wrap it in a **use-don't-cite** block, kept separate from the cited-passages block. In
    `draft_reply_node`, format `recalled` with `format_memories` and pass it as `memory`. When
    `recalled` is empty, the call must be byte-for-byte Day 4's.
11. **Inject the store into the builder.** Add a `memory=` parameter to `ticket_graph_builder` /
    `build_ticket_graph`, bind it into both nodes with `functools.partial`, `None` meaning the
    process-wide default.
12. **See it work.** Write `run_memory.py` that sends the **same** customer two related tickets and a
    **different** customer a similar one, printing what each recalled and wrote. The payoff is visible:
    the second ticket recalls the first; the third customer recalls nothing (scope). Persist to a
    `memory.db` and note that a second run recalls across processes.
13. **Test the nodes and the whole loop, offline.** Seed a fresh keyword-embedder `MemoryStore` in your
    fixture (fresh per test, so one test's write never leaks into another's recall). Assert:
    `recall_memory_node` records what the store returns; `write_memory_node` writes once then declines;
    and **end to end**, a memory written by one ticket is recalled by the next ticket from the same
    customer and reaches the draft prompt. Then fix the earlier tests your two new nodes broke — the
    node order and the notes shift, and that is part of the task.
14. **Same habit as every day**: commit on your branch, open a PR.

> **One gotcha worth naming.** Your two new nodes change the graph's node order and add two notes, so
> tests that assert on the exact `notes` list or on `notes[-1]` will break — `write_memory` now runs
> *after* `send_reply`, so the send note is no longer last. That is expected; update them. And if you
> forget to inject an offline store in the fixture, recall will try to download a real embedder mid-test.

## Expected outcome (minimum requirements)

- [ ] **`MemoryStore` reuses Day 1's embedder and BLOB/cosine helpers** — no reinvented vector code
- [ ] **`write` is idempotent on `ticket_id`** (returns `True` then `False`), embedding once on write
- [ ] **`recall` is scoped to `customer_id`**, ranked best-first, and drops sub-floor matches
- [ ] **`MEMORY_RELEVANCE` is lower than `LOW_CONFIDENCE`**, and you can say why
- [ ] **`format_memories` tags the ticket but carries no `[source]`** — background, not a citation
- [ ] **`TicketState.recalled`**, started in `initial_state`
- [ ] **`recall_memory_node`** (injected store) runs right after the lookup; **`write_memory_node`**
  runs right after the send
- [ ] **`stream_reply` takes a separate `memory` argument**; empty recall == Day 4's call exactly
- [ ] **The graph still has exactly one cycle**: `critique_retrieval -> formulate_query`
- [ ] **`run_memory.py` shows continuity and scope**: a returning customer recalls, a different one does
  not
- [ ] **Offline tests**: the store's scope/rank/idempotency, plus an end-to-end recall reaching the
  draft; earlier tests updated, not deleted
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Summarise instead of storing raw text.** Right now the memory line is the ticket text plus a tag. Add
  a cheap model call that writes a one-sentence summary instead. What does that buy you, and what new
  failure does it introduce (a summary can be *wrong* in a way a verbatim line cannot)?
- **Forget on purpose.** Memories accumulate forever. Add a TTL, or a per-customer cap that keeps the
  most recent N, or a recency weight in the ranking. Which of those would you actually want in
  production, and what does each cost you?
- **Prove the privacy property.** Write the adversarial test: customer B asks a question worded almost
  identically to customer A's past ticket, and assert B recalls **nothing** of A's. That where-clause is
  a security boundary; test it like one.
- **Make recall earn its place.** Log, over twenty mixed tickets, how often recall actually surfaced
  something and whether it helped. A memory that never fires — or fires with noise — is worse than none.
- **One store, two questions.** You now have two SQLite-backed vector stores (knowledge and memory) with
  nearly identical code. Factor the shared part out. Where does the abstraction leak — what does memory
  need that knowledge does not, and vice versa?

## If you're running out of time

Protect steps 1–3 (the store: write-once and scoped recall), step 8 and step 9 (the two nodes, wired in
the right places), and step 10 (recall reaching the draft as background). That round-trip — remember a
finished ticket, recall it on the customer's next one — is what the day is assessed on. Trim the tests
(step 13) to two cases first (idempotent scoped recall in `test_memory.py`; one end-to-end recall in
`test_graph.py`), then `run_memory.py`'s third customer (step 12 — keep the two same-customer tickets so
the continuity is visible). Do **not** drop the `customer_id` scoping or the `ticket_id` idempotency:
without scoping, one customer sees another's history; without idempotency, a resumed run poisons recall
with duplicates. Flag whatever you skipped rather than quietly leaving it out. (Coaches: see the
coaches' page "Contingency plans" for exactly what to prioritise.)
