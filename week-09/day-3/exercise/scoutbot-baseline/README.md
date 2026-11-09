# ScoutBot — Week 9 Day 3 Starting Point

This is where today starts: **Day 2's finished agent, with working RAG.** Yesterday you connected the
knowledge base to the graph — the bot **retrieves before it drafts** and **grounds its reply** in what
came back, citing the source and declining when the corpus is thin. But it retrieves exactly once, on
the **raw ticket text**. Today you make retrieval a **loop the agent drives**: it writes a search
query, judges what it got, and rewords and searches again when the result is weak — up to a bound.

What you have:

- `src/scoutbot/graph.py` — the routed, pausing, ledgered graph with Day 2's `retrieve_knowledge` node
  and a grounded `draft_reply`. Today you insert two nodes around retrieval (`formulate_query`,
  `critique_retrieval`), change `retrieve_knowledge` to search the *chosen query*, and add a back-edge
  that makes it a loop.
- `src/scoutbot/core.py` — the Anthropic calls (`triage`, `stream_reply` with its grounded prompt).
  Today you add `formulate_query`, the model call that turns a ticket into a search query.
- `src/scoutbot/knowledge.py` — chunking, embeddings, the `KnowledgeBase`, `format_passages`, and
  `LOW_CONFIDENCE`, all complete. Today you add one constant, `MAX_RETRIEVAL_ATTEMPTS`.
- `knowledge_base/` — the policy documents, and `run_rag.py` — yesterday's demo, still working.
- `tests/` — the full Day 2 suite, all passing. Today you extend the agent; keep them green.

## Three things worth knowing before you start

**1. "Agentic" means the model chooses and checks.** Day 2's retrieval was a fixed step on a fixed
input. Today the model chooses *what to search for* and the run *checks whether it worked* — and only
that check decides whether to search again. Same retrieval underneath; a loop around it.

**2. The critique should be cheap, the reword expensive.** The gate that decides whether to try again
is just the top cosine score against `LOW_CONFIDENCE` — no model call. The model call is the *reword*,
and it should only run when a free check says the last search failed. Spend the expensive thing only
when the cheap thing says to.

**3. The bound is not optional.** A loop that rewords until it succeeds never returns on a question the
corpus cannot answer. `MAX_RETRIEVAL_ATTEMPTS` is what turns self-correction into a safe, finite thing.
Every design decision today hangs off `LOW_CONFIDENCE` (when to retry) and that bound (when to stop).

## Setup

```bash
cp .env.example .env   # ANTHROPIC_API_KEY — today the query and the reply are both real calls
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
```

`fastembed` and `numpy` install with it (they arrived on Day 1).

## Run

```bash
uv run python run_rag.py        # yesterday: retrieve once, draft a grounded, cited reply
uv run python run_retrieve.py   # Day 1: build the index, retrieve against real questions (no model call)
uv run python run_approval.py   # Week 8 Thursday: policy, pause, send once
uv run python main.py           # Week 7's loop, unchanged
uv run pytest                   # the Day 2 suite, passing, before you change anything
```
