# W09 D1 - Knowledge base plan

Give triage a searchable policy knowledge base, stored in PostgreSQL with pgvector.

```text
make kb-index:  data/knowledge_base/*.md → chunks → fastembed → PostgreSQL

make run:       get_customer → retrieve_knowledge → triage → review or done
                                     │                ▲
                 ticket text → query embedding        │
                                     │                │
                               PostgreSQL ──── top k passages
```

## Decisions

| Topic | Choice | Why |
| --- | --- | --- |
| Database | `pgvector/pgvector:0.8.7-pg18-trixie` | PostgreSQL 18 with the `vector` extension |
| Python driver | `psycopg[binary]` 3.3 and `pgvector` 0.5 | Binary build and `register_vector` work on Python 3.14 |
| Embeddings | `fastembed` 0.9, `BAAI/bge-small-en-v1.5` | Local, no PyTorch, 384 dimensions |
| Column type | `vector(384)` | Simple, and has cosine distance (`<=>`) |
| Search | Exact, no index at first | About 50 rows; exact search has perfect recall |
| Checkpoints | Stay in SQLite | Moving them is a separate change |
| Knowledge base | `data/knowledge_base/` | The app stays self-contained |
| Chunks | 60 words, overlap 20 | See step 21 |

The exercise text asks for SQLite BLOBs and no graph change. The user story takes
priority: PostgreSQL, and connected to the bot.

Facts to respect:

- Mount the PostgreSQL 18 volume at `/var/lib/postgresql`, not `.../data`. The old path
  can lose data when the container is recreated.
- Publish PostgreSQL on the host as `127.0.0.1:5432:5432` only.
- fastembed's default model cache is in the temp directory. Set a persistent `cache_dir`.
- `make run` must not download anything: load the model with `local_files_only=True`.
  Only `make kb-index` may download it.
- Set `HF_HUB_DISABLE_TELEMETRY=1` before any model download.
- New state types must join `CHECKPOINT_TYPES`, or they will not load back on resume.
- Only ids, counts, source names and scores go to `safe_log`. Never ticket text, queries
  or passages.

## Phase A: PostgreSQL

1. [x] `database/docker-compose.yml`: pinned image, port on `127.0.0.1:5432`, named
   volume, health check with `pg_isready`. Credentials in a git-ignored `database/.env`,
   with a `.env.example`.
2. [x] `make db-up`, `make db-down`, `make db-check`. Check that `CREATE EXTENSION
   vector` works and that data survives a container restart.
3. [x] Add dependencies with upper bounds: `fastembed>=0.9,<0.10`, `numpy>=1.26,<3`,
   `psycopg[binary]>=3.3,<4`, `pgvector>=0.5,<0.6`.
4. [x] Settings: `KNOWLEDGE_DATABASE_URL` (secret), model name, model cache path, chunk
   size, overlap, `k`. Update `.env.example`; the user adds the URL to `.env`.

## Phase B: Chunks and embeddings

5. [x] The five policy files are in `data/knowledge_base/`.
6. [x] `knowledge/chunking.py`: `chunk_document(text, size, overlap)` makes word windows,
   keeps the short tail and rejects `overlap >= size`. `chunk_corpus(docs)` adds `source`
   and `ordinal`. Tests.
7. [x] `knowledge/embedder.py`: `fastembed_embedder()` with the import inside. It uses
   `passage_embed` for chunks and `query_embed` for queries. Everything else depends on
   a small `Embedder` protocol, so tests use a fake.

## Phase C: Store and search

8. [x] Schema, created idempotently:
   - `knowledge_indexes`: `model`, `chunk_size`, `chunk_overlap`, `corpus_hash`, unique
     on the first three.
   - `knowledge_chunks`: `index_id`, `source`, `ordinal`, `text`, `embedding vector(384)`.
9. [x] `KnowledgeBase.build(docs)`: skip if `corpus_hash` is unchanged, otherwise replace
   that index's chunks in one transaction. This avoids embedding on every start.
10. [x] `KnowledgeBase.search(query, k)`: rank by `embedding <=> query`, return `source`,
    `ordinal`, `text` and `score = 1 - distance`. An empty store returns `[]`. Refuse an
    index built with a different model.
11. [x] CLI `ticket-classifier kb-index` and `make kb-index`. It reports chunk count and
    whether it reused the index.
12. [x] Tests against a separate `knowledge_test` database, run by `make test-db` and
    skipped by `make test`. One real fastembed test, skipped by default.

## Phase D: Connect to the bot

13. [x] `KnowledgePassage` in `models/`, `knowledge` key in `TriageState` (`NotRequired`),
    and the type in `CHECKPOINT_TYPES`.
14. [x] Node `retrieve_knowledge` between `get_customer` and `triage`, using the ticket
    text as the query. Saved threads without the key must still run and resume.
15. [x] `create_prompt`: add passages in `<policy source="...">` tags. Update the system
    prompt: policies inform the classification, ticket text stays untrusted.
16. [x] Show the passage sources to the human reviewer in the pause request.
17. [x] Before the first ticket, fail with a clear message if the database is down or
    the index is missing, so no API money is spent.
18. [x] Telemetry: span attributes and a `safe_log` line with passage count, top score
    and source names. Test that no passage or query text is exported.
19. [ ] One real end-to-end check with `make run`. **Costs money: ask first.**

## Phase E: Experiments (no API cost)

20. [x] Small labelled question set: refund, shipping, warranty with no shared keywords,
    and one question the corpus cannot answer.
21. [x] Compare chunk sizes 30, 60 and 120 with overlaps 0, 10 and 20: hit rate at 1 and
    3, mean reciprocal rank, chunk count. Pick the default from the results.

    `make kb-eval`, 14 answerable questions (one question is 0.07):

    | Size | Overlap | Chunks | Hit@1 | Hit@3 | MRR |
    | ---: | ---: | ---: | ---: | ---: | ---: |
    | 120 | 20 | 14 | 0.79 | 1.00 | 0.89 |
    | 90 | 20 | 17 | 0.79 | 0.93 | 0.86 |
    | 80 | 10 | 19 | 0.79 | 0.93 | 0.85 |
    | 60 | 20 | 29 | 0.79 | 0.93 | 0.83 |
    | 60 | 10 | 25 | 0.71 | 0.79 | 0.74 |
    | 60 | 0 | 21 | 0.50 | 0.93 | 0.69 |
    | 30 | 20 | 108 | 0.57 | 0.57 | 0.57 |
    | 30 | 0 | 41 | 0.43 | 0.64 | 0.52 |

    - 30 words is too small: little meaning per chunk, and answers are cut at edges.
    - Overlap helps: 60/20 beats 60/10.
    - From 60/20 to 120/20 the results differ by one or two questions, and they go up
      and down with the overlap: noise. Telling them apart needs more questions.
    - With 14 chunks, three passages cover a fifth of the corpus, so 120 wins partly
      by finding the right document, not the right passage.
    - Default: 60/20. Same hit@1 as the larger settings, half the prompt text of 120.
22. [ ] Compare the top score of real hits and the out-of-corpus question. Set a minimum
    score, so weak passages do not reach the prompt.
23. [ ] Data types: compare `vector`, `halfvec`, `bytea` and `real[]` on size, operators,
    index support and ease of use. Check pgvector's scores against a numpy cosine.

## Phase F: Far-reaching goals

24. [ ] PostgreSQL full-text search: generated `tsvector` column, GIN index,
    `websearch_to_tsquery`, `ts_rank_cd`. Compare with vector search on the question set.
25. [ ] Optional: hybrid search with reciprocal rank fusion, only if step 24 shows
    queries that vector search misses.
26. [ ] Optional: time exact search on a larger synthetic corpus and compare with HNSW
    (`vector_cosine_ops`).
27. [ ] Update `README.md` and `docs/conventions.md`.

## Phase G: Type checks (after the user story)

28. [ ] Pick a type checker for Python 3.14 (mypy, pyright or ty), from the official
    docs. Add it to the dev dependencies and to `make lint`.
29. [ ] Fix the errors it finds, without `Any` or `# type: ignore` where a real type
    exists.

## Docs

- [pgvector](https://github.com/pgvector/pgvector)
- [pgvector-python](https://github.com/pgvector/pgvector-python)
- [psycopg 3 installation](https://www.psycopg.org/psycopg3/docs/basic/install.html)
- [FastEmbed](https://qdrant.github.io/fastembed/)
- [PostgreSQL Docker image](https://hub.docker.com/_/postgres)
- [PostgreSQL 18 text search](https://www.postgresql.org/docs/18/textsearch-controls.html)
