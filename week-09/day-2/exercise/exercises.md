# W9D2 Exercise — Make ScoutBot Answer From the Source

## Scenario

Yesterday you gave ScoutBot a knowledge base and a `search()` that returns the passages most likely to
answer a question. It works — and nothing uses it. A ticket still gets a reply written from the model's
memory, so *how long does a refund take?* still comes back "three to five days" when your policy says
five, with nothing behind the number.

Today you close the loop. You will insert a **retrieval step** into the graph, then make **`draft_reply`
ground its answer in what was retrieved** — cite the policy it used, and, when retrieval comes back
weak, say a teammate will follow up instead of guessing. This is basic RAG: retrieve, then generate
from what you retrieved. By the end, the same question returns a reply that cites `[refunds]` and states
your real five-day window — and a question your policies do not cover returns an honest "we'll get back
to you" rather than a confident invention.

## Starting point

`scoutbot-baseline/` is **Day 1's finished agent**, knowledge base included. Everyone extends this same
baseline, in place. Three things to know:

- **`knowledge.py` is done.** You have `KnowledgeBase.search(query, k)` returning ranked
  `Retrieved(source, ordinal, text, score)`. You call it today; you do not rebuild it.
- **You are touching the graph today** — unlike yesterday. One new node, one changed node, one new
  edge. The rest of the graph does not move.
- **No new dependency, no LangChain.** Grounding is retrieved text in the prompt plus an instruction.
  Every model call still goes through the Anthropic SDK directly.

## Your task

Working in pairs, on a new branch:

### Part 1 — Ground the generation (`core.py` and two helpers in `knowledge.py`)

1. **Format passages for a prompt.** In `knowledge.py`, write `format_passages(passages)` that renders
   a list of hits as one tagged line each: `[refunds] refunds are issued within five business days`.
   Make it accept **either** `Retrieved` objects **or** plain dicts (`{"source":..., "text":...}`),
   because the graph will keep passages in state as dicts. The tag it prints is the citation the model
   will echo, so keep it to `[source]` and the text — no scores, no ordinals.
2. **Name the confidence line.** In `knowledge.py`, add a `LOW_CONFIDENCE` constant (start at `0.5`) —
   the top cosine score below which you will treat retrieval as a miss. A named constant, not a magic
   number buried in a node.
3. **Teach `stream_reply` to ground.** In `core.py`, add a `knowledge: str = ""` argument to
   `stream_reply`. When it is empty, behave exactly as today (the ungrounded `DRAFT_SYSTEM`). When it
   carries passages: switch to a **second system prompt** that says *answer using only these passages,
   cite the `[source]` you used, and if they do not cover the question say a teammate will follow up
   rather than inventing anything* — and put the passages in the user message. Keep everything else
   (the streaming, the callback) identical.

### Part 2 — Retrieve inside the graph (`graph.py`), then a demo and tests

4. **Give the state a place for passages.** Add a `retrieved: list[dict]` field to `TicketState` (and
   start it empty in `initial_state`). Dicts, not `Retrieved` objects, so the checkpointer can
   serialise them.
5. **Write the retrieval node.** `retrieve_knowledge_node(state, kb=None)` searches the knowledge base
   for `state["ticket_text"]`, writes the top passages into `retrieved` as dicts, and adds a note. When
   the best score is under `LOW_CONFIDENCE`, say so in the note. **Inject the store**: `kb` is a
   parameter, defaulting to a lazily-built process-wide base, exactly as `ledger` is on `send_reply` —
   so a test can pass a fake-embedder store.
6. **Wire it in.** Insert `retrieve_knowledge` between `triage_ticket` and `draft_reply` (bind `kb`
   with `functools.partial`, like the ledger). Then make `draft_reply_node` call `format_passages` on
   `state["retrieved"]` and pass the result to `stream_reply(..., knowledge=...)`. That one argument is
   the whole switch from recalled to grounded.
7. **See it work.** Write `run_rag.py` that builds/opens `knowledge.db`, builds the graph with that
   store, and runs a few tickets — including **one the corpus does not cover** — printing the retrieved
   passages, their scores, and the grounded reply. The covered ones should cite a `[source]`; the
   uncovered one should decline.
8. **Test it, offline.** With a hand-written keyword embedder (borrow yesterday's), seed a fake
   knowledge base and assert: the node writes dicts and ranks the on-topic passage first; a low-score
   query is flagged; the draft call switches to the grounded system prompt and carries the passages
   when `retrieved` is set, and stays ungrounded when it is empty. **The graph now retrieves on every
   ticket**, so point its process-wide store at your fake in a fixture — or the suite will try to
   download a model.
9. **Same habit as every day**: commit on your branch, open a PR. Confirm the earlier tests still pass.

> **One gotcha you may hit.** The moment retrieval runs inside a *streamed* graph, SQLite may complain
> that the connection was "created in a thread… used in another thread." LangGraph runs nodes on worker
> threads. The fix is the same one the checkpointer uses — open the store's connection with
> `check_same_thread=False`. Find where `KnowledgeBase` connects and add it.

## Expected outcome (minimum requirements)

- [ ] **`format_passages` renders `[source] text` lines** and accepts both `Retrieved` objects and dicts
- [ ] **`LOW_CONFIDENCE` is a named constant**, used to flag weak retrieval rather than a bare number
- [ ] **`stream_reply(..., knowledge=...)` grounds and cites** with a second system prompt, and is
  unchanged when `knowledge` is empty
- [ ] **`TicketState` has a `retrieved` field** of JSON-serialisable dicts, started empty in
  `initial_state`
- [ ] **`retrieve_knowledge_node` searches, records passages and notes confidence**, and takes the
  knowledge base as an **injected** parameter
- [ ] **The node sits between triage and drafting**, and `draft_reply` grounds on what it wrote
- [ ] **`run_rag.py` shows a grounded, cited reply** for a covered question and a **refusal** for an
  uncovered one
- [ ] **Offline tests** for the node and the grounded draft, with the graph's store pointed at a fake
  embedder so nothing downloads a model
- [ ] Earlier tests still pass; work is on a branch with an open pull request

## If you finish early

- **Prove the refusal is real.** Find a question just outside the corpus (say, international customs)
  and confirm the reply declines rather than inventing a figure. Then add one sentence to a policy doc
  that answers it, rebuild, and watch the same question start citing it. Retrieval quality *is* answer
  quality — you just changed the answer without touching the model.
- **Cite precisely.** Right now a passage is tagged by its document (`[refunds]`). Add the chunk's
  ordinal so a citation points at the exact passage (`[refunds #2]`), and check the model reproduces it.
  Where does more precision help a reviewer, and where does it just add noise?
- **Tighten the threshold and measure.** Move `LOW_CONFIDENCE` to `0.6`. How many real hits does it now
  wrongly refuse, and how many misses does it correctly catch? You are tuning precision against recall
  by hand — the thing Wednesday and Thursday automate.
- **Ground the escalation too.** When a ticket pauses for a human, the passages are already in state.
  Add them to the approval payload so the reviewer sees *what the draft was based on*, not just the
  draft. A grounded approval is a faster approval.

## If you're running out of time

Protect steps 3, 5, and 6: the grounded `stream_reply`, the retrieval node, and wiring it into the
graph so a real ticket comes back cited. That end-to-end path — retrieve, ground, cite — is what the
day is assessed on. Trim the test suite (step 8) to two cases first (node writes/ranks; grounded draft
carries passages), then `run_rag.py`'s extra tickets (step 7 — keep at least the covered one and the
uncovered one). Do **not** skip the low-confidence refusal: a bot that grounds when it can and declines
when it cannot is the whole point, and the confident wrong answer is exactly what today exists to kill.
Flag whatever you skipped rather than quietly leaving it out. (Coaches: see the coaches' page
"Contingency plans" for exactly what to prioritise.)
