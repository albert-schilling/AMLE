# W9D1 Exercise — Give ScoutBot Something to Look Things Up In

## Scenario

Your agent can triage a ticket, route it, draft a reply, pause for the right human, send once, and
trace itself. But ask it a plain policy question — *how long does a refund to a bank transfer take?* —
and it answers from the model's memory, not from your company's actual policy. Sometimes that memory is
right. Sometimes it invents "3 to 5 days" because that sounds like a refund. There is nothing grounding
the reply in what your policies really say.

Today you build the missing piece: **retrieval.** You will take a folder of policy documents, cut them
into chunks, turn each chunk into an embedding — a vector positioned by *meaning* — store the vectors,
and, given a question, return the passages most likely to answer it. No model reasoning today and
nothing sent to a customer: a question goes in, ranked passages come out. Tomorrow those passages
ground `draft_reply`. Today's whole job is to make retrieval work and to understand *why* a vector of
floats can tell that "how long do refunds take" and "refunds are issued within five business days" are
about the same thing.

## Starting point

`scoutbot-baseline/` is Week 8's finished agent, unchanged, plus a new `knowledge_base/` folder of
policy documents. **Everyone extends this same baseline today, in place.** Four things to know:

- **Two things to install**, the first since Week 8 Day 5: `uv add "fastembed>=0.8,<0.9" "numpy>=1.26,<3"`. `fastembed`
  is the embedding model runner; it runs on ONNX Runtime, so it pulls **no PyTorch** and installs
  cleanly across machines. The first time you embed, it downloads a ~130MB model once and caches it;
  after that, retrieval is fully offline.
- **You are not touching the graph today.** `knowledge.py` is a new module that sits *beside* the
  agent. Wiring retrieval into `draft_reply` is tomorrow.
- **Anthropic has no embeddings API.** This is the one piece that comes from outside the SDK you have
  used all along. That is why there is a new dependency at all.
- **`loop.py` still doesn't change**, and the Week 8 tests should still pass when you're done.

## Your task

Working in pairs, on a new branch, adding a new `src/scoutbot/knowledge.py` (and a `run_retrieve.py`):

### Part 1 — Embeddings and similarity (the one idea the day rests on)

1. **Embed two sentences and look at what you get.** Using `fastembed`'s `TextEmbedding` with
   `BAAI/bge-small-en-v1.5`, embed `"how long do refunds take?"` and `"refunds are issued within five
   business days"`. Confirm each is a vector of the same length (384 floats). These share almost no
   words — that is the point.
2. **Measure closeness with cosine similarity.** Write a `cosine_scores(matrix, query)` that returns
   the cosine similarity between a query vector and each row of a matrix. Embed a third, unrelated
   sentence (`"the warranty covers manufacturing defects"`) and confirm the two refund sentences score
   *high* against each other and the warranty one scores *low*. **Keep this function pure and free of
   any model** — you will test it with hand-made `[1,0,0]`-style vectors, so it must not import
   fastembed.
3. **Wrap the embedder behind a plain function.** Write `fastembed_embedder()` that returns a function
   `texts -> list of float32 vectors`, with the `fastembed` import *inside* it. Everything else in your
   module should depend on that function type, never on fastembed directly. This is what will let you
   test the whole store with a fake embedder and no download.

### Part 2 — Chunking, the store, and retrieval end to end

4. **Chunk a document.** Write `chunk_document(text, size, overlap)` that cuts text into overlapping
   windows of `size` words, stepping by `size - overlap`. Keep the final short window rather than
   dropping it, and reject `overlap >= size`. Then `chunk_corpus(docs)` over a `{source: text}` dict,
   tagging each chunk with its `source` document and its `ordinal` position — you will need both to cite
   a passage tomorrow.
5. **Build a vector store on SQLite — no vector database.** Write a `KnowledgeBase` that stores each
   chunk's `source`, `ordinal`, `text`, and its vector as a `float32` **BLOB** in an ordinary SQLite
   table. A vector is just `np.float32(vec).tobytes()`; read it back with `np.frombuffer(...,
   dtype=np.float32)`. Do **not** reach for `sqlite-vec` or Chroma — a BLOB column and numpy are the
   whole store, and they avoid a real cross-platform trap (the `sqlite-vec` extension often won't load
   on system Python).
6. **Search it.** Give `KnowledgeBase.search(query, k)` that embeds the query with the *same* embedder
   the chunks used, ranks every stored vector by cosine, and returns the top `k` as `(source, ordinal,
   text, score)`. An empty store returns an empty list, not an error.
7. **Index the real corpus and retrieve against real questions.** Write `run_retrieve.py` that builds
   the store from `knowledge_base/` into a `knowledge.db` file, then prints the top passages for a few
   support questions (a refund one, a shipping one, a warranty one worded with *no* shared keywords).
   Include **one question the corpus cannot answer** ("what is the capital of France?") and look at its
   top score next to a real hit's. What is the gap, and what would you do with it? (That gap is the hook
   for Wednesday and Thursday.)
8. **Persist and reopen.** Point the store at a file, build it, close it, and open a *fresh*
   `KnowledgeBase` on the same file. It should search without re-indexing. The knowledge now lives in
   the same kind of SQLite file the checkpointer uses — knowledge next to state.
9. **Write tests, offline.** With a hand-written keyword embedder (a few lines, no model), assert:
   chunking produces the right windows and keeps the tail; `cosine_scores` ranks by direction and does
   not return `nan` on a zero vector; `search` returns the right chunk first and reports a score;
   `build` indexes every chunk; a file-backed store reopens. Keep **exactly one** test that uses the
   real `fastembed` embedder, and skip it by default (e.g. behind an env var), so the suite stays fast
   and offline.
10. **Same habit as every day**: commit on your branch, open a PR back to main. Confirm the Week 8
    tests still pass untouched — you added a module, you did not change the agent.

## Expected outcome (minimum requirements)

- [ ] **`fastembed` and `numpy` installed**, and no vector-database or SQLite-extension dependency added
- [ ] **`cosine_scores` is a pure function** that ranks vectors by direction, tested with hand-made
  vectors and no model
- [ ] **The embedder is injected, not imported** — a `fastembed_embedder()` factory with the import
  inside it, and a store that depends only on the function type
- [ ] **`chunk_document` produces overlapping word windows**, keeps the short tail, and rejects
  `overlap >= size`; chunks carry their `source` and `ordinal`
- [ ] **A `KnowledgeBase` stores vectors as `float32` BLOBs in ordinary SQLite** — no vector DB, no
  extension
- [ ] **`search(query, k)` returns the top-k passages with scores**, embedding the query with the same
  embedder as the chunks, and returns `[]` on an empty store
- [ ] **`run_retrieve.py` retrieves sensible passages** for real questions, including a warranty
  question worded with no shared keywords, and shows a visibly lower score for an out-of-corpus question
- [ ] **A file-backed store reopens and searches without re-indexing**
- [ ] **Offline tests** covering chunking, cosine, and search ranking; exactly one real-embedding test,
  skipped by default
- [ ] Week 8's existing tests still pass, untouched
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Prove embeddings beat keyword search.** Find a question that a keyword search (`"refund" in text`)
  would miss but your retriever gets right — different words, same meaning. This is the single most
  convincing demo of what an embedding buys you; keep the example for tomorrow.
- **Vary the chunk size and watch retrieval change.** Rebuild with `size=30` and `size=120`. Does a big
  chunk dilute the score of a small relevant fact? Does a tiny chunk lose the context around it? There
  is no single right answer; there is a trade-off, and feeling it is the exercise.
- **Return the score honestly.** Add a threshold to `run_retrieve.py`: below some cosine score, print
  "the corpus probably does not answer this" instead of a passage. Where did you set the line, and how
  many real hits did it wrongly reject? (You have just met the precision/recall trade-off that the
  agentic days automate.)
- **Store the model name next to the vectors.** A store built with one embedding model cannot be
  searched with another — the vectors are not comparable. Add the model name to the table and refuse a
  query embedded by a different model. That one check prevents a whole class of silent, baffling bugs.
- **Time it.** Embed the corpus and measure: how long to embed 25 chunks, how long for one query, how
  long is the cosine search itself? At what corpus size would the brute-force search stop being instant,
  and what would you reach for then (an approximate index)?

## If you're running out of time

Protect steps 4–7: chunking, the BLOB store, `search`, and `run_retrieve.py` retrieving against the
real corpus. Seeing a warranty question with no shared keywords pull back the warranty passage is what
the day is assessed on. Trim the test suite (step 9) to two or three cases first, then the persist-and-
reopen check (step 8 — say you did it in one process), then Part 1's exploratory steps 1–2 (you can go
straight to the module). Do **not** skip step 7's out-of-corpus question: the low score for a miss is
the hook the whole rest of the week hangs on. Flag whatever you skipped rather than quietly leaving it
out. (Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)
