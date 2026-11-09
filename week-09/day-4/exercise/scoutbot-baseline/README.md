# ScoutBot — Week 9 Day 4 Starting Point

This is where today starts: **Day 3's finished agent, with agentic RAG.** Yesterday you made retrieval
a loop the agent drives — it **writes a search query**, **critiques** what came back, and **rewords and
searches again** when the result is weak, bounded by `MAX_RETRIEVAL_ATTEMPTS`. But it runs that whole
loop on **every** ticket, including a "thanks, that's all!" that the policy corpus could never help
with. Today you put a **router** in front of retrieval: a node that classifies each ticket and decides
*how hard to retrieve* — not at all, once, or the full loop.

What you have:

- `src/scoutbot/graph.py` — the routed, pausing, ledgered graph with Day 3's retrieval loop
  (`formulate_query` → `retrieve_knowledge` → `critique_retrieval`, with a bounded back-edge). Today you
  insert one node before the loop (`classify_query`), add one router (`route_query`), and add one clause
  to `route_after_critique` so a single-shot route does not loop.
- `src/scoutbot/core.py` — the Anthropic calls (`triage`, `formulate_query`, `stream_reply`). Today you
  add `classify_query`, the model call that picks a retrieval strategy.
- `src/scoutbot/schema.py` — `Category` and `Priority` enums. Today you add `QueryRoute`.
- `src/scoutbot/knowledge.py` — chunking, embeddings, the `KnowledgeBase`, `LOW_CONFIDENCE`,
  `MAX_RETRIEVAL_ATTEMPTS`, all complete and untouched today.
- `knowledge_base/` — the policy documents, and `run_agentic.py` — yesterday's loop demo, still working.
- `tests/` — the full Day 3 suite, all passing. Today you extend the agent; keep them green.

## Three things worth knowing before you start

**1. "Adaptive" means effort matched to the question.** Day 3 spent the same loop on every ticket.
Today a cheap classifier reads the ticket and picks: `direct` (no search — a greeting, a thank-you),
`retrieve` (one search — a clear policy question), or `iterative` (Day 3's full loop — anything oblique
or account-specific). Same loop underneath; a fork in front of it.

**2. The safe default is *more* retrieval, never less.** Your router is a model call, and model calls
are fallible. When it returns something you do not recognise, fall back to `iterative`. Erring toward a
bigger search wastes a little; erring toward `direct` skips retrieval on a real question and lets the
model guess — the exact failure this week exists to prevent.

**3. Keep exactly one cycle.** Day 3's back-edge (`critique_retrieval → formulate_query`) is the only
loop in the graph, and it must stay the only one. `direct` skips the loop entirely; `retrieve` enters
it but must not reword. If your wiring grows a second cycle, or a single-shot ticket starts looping, the
day's shape has broken.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — today routing, the query, and the reply are all real calls
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

`fastembed` and `numpy` install with it (they arrived on Day 1). Nothing new installs today.

## Run

```bash
uv run python run_agentic.py    # yesterday: formulate a query, retrieve, critique, reword, then draft
uv run python run_rag.py        # Day 2: retrieve once, draft a grounded, cited reply
uv run python run_retrieve.py   # Day 1: build the index, retrieve against real questions (no model call)
uv run python run_approval.py   # Week 8 Thursday: policy, pause, send once
uv run python main.py           # Week 7's loop, unchanged
uv run pytest                   # the Day 3 suite, passing, before you change anything
```
