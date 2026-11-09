# ScoutBot — Week 9 Day 2 Starting Point

This is where today starts: **Day 1's finished agent, with a working knowledge base.** Yesterday you
built retrieval — chunking, embeddings, a `KnowledgeBase` over SQLite BLOBs, and `search()` returning
ranked passages — and stopped there, at "here are the passages that match." Today you connect it: the
graph will **retrieve before it drafts**, and the draft will be **grounded in what was retrieved**,
citing its source and declining when the corpus does not cover the question.

What you have:

- `src/scoutbot/knowledge.py` — **yesterday's deliverable, complete.** `chunk_document`,
  `fastembed_embedder`, and a `KnowledgeBase` whose `search(query, k)` returns the top passages as
  `Retrieved(source, ordinal, text, score)`. You will call this today, and add two small helpers to it.
- `src/scoutbot/graph.py` — `TicketState` and the routed, pausing, ledgered graph. `draft_reply_node`
  still writes the reply from the ticket and its triage alone; today you insert a retrieval node before
  it and feed what it finds into the draft.
- `src/scoutbot/core.py` — the Anthropic calls (`triage`, `stream_reply`). Every model call goes
  through the SDK directly; there is no LangChain, and today adds none. You will teach `stream_reply`
  to take retrieved passages and ground its answer in them.
- `knowledge_base/` — the five policy documents, and `run_retrieve.py` — yesterday's demo, still
  working.
- `tests/` — the full Day 1 suite, all passing. Today you extend the agent; keep them green.

## Three things worth knowing before you start

**1. "RAG" is not a framework here.** It is two steps: retrieve some text, then put that text in the
prompt and tell the model to use only it. You already have the retrieval half. Today's generation half
is a system prompt and a keyword argument — no new dependency, no LangChain.

**2. The score is a signal, not just a sort key.** `search()` gives each hit a cosine score. A top hit
that scores *low* means the corpus probably does not answer the question — and a grounded reply should
say a teammate will follow up rather than invent a number. Deciding where "low" is, and what to do
about it, is half of today.

**3. Inject the knowledge base, do not import a model.** Pass the `KnowledgeBase` into your retrieval
node the way the ledger is passed into `send_reply`, so a test can hand it a fake-embedder store and
run the whole graph with no download. If a node reaches for `fastembed` itself, the test suite stops
being offline.

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — today's demo drafts a real reply, so it is needed
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

`fastembed` and `numpy` install with it (they arrived yesterday).

## Run

```bash
uv run python run_retrieve.py   # yesterday: build the index, retrieve against real questions (no model call)
uv run python run_approval.py   # Week 8 Thursday: policy, pause, send once
uv run python main.py           # Week 7's loop, unchanged
uv run pytest                   # the Day 1 suite, passing, before you change anything
```
