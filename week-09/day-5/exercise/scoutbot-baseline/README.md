# ScoutBot — Week 9 Day 5 Starting Point

This is where today starts: **Day 4's finished agent, with adaptive RAG.** Yesterday you put a **router**
in front of retrieval — a cheap classifier that reads each ticket and decides how hard to look: `direct`
(no search), `retrieve` (one search), or `iterative` (the full bounded loop). But every run still begins
from nothing. A customer who wrote in an hour ago is a stranger now — the checkpointer remembers a *run*,
and nothing remembers a *person*. Today you give ScoutBot a **cross-ticket, per-customer memory**: it
recalls a customer's relevant past tickets before it drafts, and remembers each finished ticket after.

What you have:

- `src/scoutbot/knowledge.py` — chunking, the injected embedder (`fastembed_embedder`, `EmbedFn`), the
  `float32`-in-SQLite BLOB helpers (`_to_blob`/`_from_blob`), `cosine_scores`, and the `KnowledgeBase`.
  **This is the machinery you reuse today** — memory is this store scoped to a customer. Untouched today.
- `src/scoutbot/graph.py` — the routed, pausing, ledgered, traced graph. Today you insert one node near
  the front (recall) and one at the very end (write), and add one state field. The retrieval loop and the
  approval branch do **not** move.
- `src/scoutbot/core.py` — the Anthropic calls (`triage`, `formulate_query`, `classify_query`,
  `stream_reply`). Today you give `stream_reply` one new argument so recalled memory rides into the draft
  as background.
- `knowledge_base/` — the policy documents, and `run_router.py` — yesterday's routing demo, still working.
- `tests/` — the full Day 4 suite, all passing. Today you extend the agent; your two new nodes will shift
  the node order and the notes, so expect to update some of these — that is part of the task.

## Three things worth knowing before you start

**1. Memory is the knowledge base pointed at a different question.** Knowledge is one shared corpus,
**retrieved** and **cited** — *"what does our policy say?"*. Memory is many small, per-customer records,
**recalled** as background and **never cited** — *"what do we already know about this person?"*. Same
embedder, same vectors-in-SQLite, same cosine. The differences are **scope** (a `customer_id` column that
recall filters on — that is the whole privacy property) and **writing once** (idempotent on `ticket_id`,
the send-ledger's discipline again). Reuse `knowledge.py`'s parts; don't reinvent them.

**2. Memory is background, not a source.** Recalled lines reach the draft in a **use-don't-cite** block,
kept separate from the cited policy passages. A grounded reply still cites only policy; memory makes the
answer read like a continuation. Keep the two blocks distinct, and give `format_memories` a shape that is
deliberately *unlike* `format_passages` — no `[source]` tag. A memory dressed as a citation is the exact
confusion to avoid.

**3. Recall errs toward remembering; retrieval errs toward silence.** Set the memory relevance floor
*below* `knowledge.LOW_CONFIDENCE`. A weak retrieval grounds a factual reply, so it must stay out; a weak
recall only adds reviewed background, so surfacing a loosely-related past ticket is cheap and missing a
relevant one is not.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — triage, routing, the query, and the reply are all real calls
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

`fastembed` and `numpy` install with it (they arrived on Day 1). Nothing new installs today — memory
reuses the corpus's embedder.

## Run

```bash
uv run python run_router.py     # yesterday: classify the ticket, then retrieve as hard as it deserves
uv run python run_agentic.py    # Day 3: formulate a query, retrieve, critique, reword, then draft
uv run python run_rag.py        # Day 2: retrieve once, draft a grounded, cited reply
uv run python run_retrieve.py   # Day 1: build the index, retrieve against real questions (no model call)
uv run python run_approval.py   # Week 8 Thursday: policy, pause, send once
uv run python main.py           # Week 7's loop, unchanged
uv run pytest                   # the Day 4 suite, passing, before you change anything
```
