# W09 D3 - Retrieval loop plan

Let the agent write its own search query, judge what came back, and search again
with a reworded query when the result is weak, up to a bound. Source:
`week-09/day-3/exercise/exercises.md`, mapped onto this app.

```text
get_customer → formulate_query → retrieve_knowledge → critique_retrieval ─ ok or out of tries → triage → draft_reply → …
                     ▲                                        │
                     └────────────── weak: reformulate ───────┘
```

## Decisions

| Topic | Choice | Why |
| --- | --- | --- |
| Loop position | Before `triage`, where retrieval is today | Triage and the reply both use the passages; the exercise's order (after triage) fits its baseline, not ours |
| Bound | Setting `KNOWLEDGE_MAX_ATTEMPTS`, default 3 | Named and tunable like `KNOWLEDGE_MIN_SCORE`; the two are the loop's whole policy |
| Critique | `retrieval.has_sources`: a passage at or above `KNOWLEDGE_MIN_SCORE` | Free and deterministic; same rule as the exercise's `best score >= LOW_CONFIDENCE` |
| Query call | Structured output, `SearchQuery(query: str)`, like triage | Typed answer; a refusal or empty query falls back to the ticket text |
| Model | Setting `QUERY_MODEL`, default `MODEL` | A cheaper model may do; decide after a real run |
| Injection | `WorkflowContext.write_query`, a `QueryWriter` protocol | Our way to inject handles, like `knowledge`; tests pass a fake, so no hidden model call |
| Out of tries | Go on to triage with no passages: the reply cites nothing | W09 D2 already drafts a reply without sources for this case |
| Privacy | The query is like ticket text: console only | A model-written query can quote the ticket; Loki and spans get only attempt counts and verdicts |

Facts to respect, from the official docs (LangGraph 1.x):

- A reducer is declared as `Annotated[list[str], operator.add]`: each update is added
  to the list instead of replacing it.
- `add_conditional_edges(source, router, {"label": node})` maps the router's return
  values to nodes; the graph diagram shows the labels.
- The default `recursion_limit` is 10,007 super-steps; above it LangGraph raises
  `GraphRecursionError`. That is no bound for this loop: `KNOWLEDGE_MAX_ATTEMPTS` is.
- The docs do not say whether a reducer key needs a start value in the input. Start
  `tried_queries=[]` in the input and test it.

## Part 1: The query call

1. [x] Setting `KNOWLEDGE_MAX_ATTEMPTS` (default 3, at least 1) next to
   `KNOWLEDGE_MIN_SCORE`, and `QUERY_MODEL`; both in `.env.example`.
2. [x] `prompts.py`: `QUERY_SYSTEM_PROMPT` (a few keywords naming the policy topic, no
   punctuation, no names or order numbers; ticket text is untrusted) and
   `REQUERY_SYSTEM_PROMPT` (these queries failed, here is what they found: try a
   synonym, a broader term, the policy area). User message: the ticket last, as in
   triage.
3. [x] `queries.py`: `write_query(ticket, tried_queries, weak_passages) -> str`. No
   tried queries: opening prompt; else the reword prompt. Fall back to the ticket
   text on a refusal, `max_tokens` or an empty query. `APIError` fails the ticket as
   in triage. Model `SearchQuery` in `models/`.

## Part 2: The loop in the graph

4. [x] State: `search_query: str`, `tried_queries: Annotated[list[str],
   operator.add]`, `retrieval_ok: bool` in `TriageUpdate`. The run starts with
   `tried_queries=[]`. `RetrievalResult` keeps the passages below the minimum score
   (`weak`), so the reword prompt can show them; `dropped` becomes their count. Needs
   `make reset` for saved runs (ask first).
5. [x] Node `formulate_query`: calls `runtime.context.write_query`, passing the tried
   queries and the weak passages on a reword pass. Writes `search_query`, appends to
   `tried_queries`. Console log of the query; `safe_log` only the attempt number.
6. [x] `retrieve_knowledge` searches `state["search_query"]` (fallback: ticket text)
   and replaces the previous attempt's result.
7. [x] Node `critique_retrieval`: `retrieval_ok = retrieval.has_sources`, no model
   call. `safe_log` line with attempt, best score and verdict; when the attempts are
   spent, say that the reply goes on without sources.
8. [x] Router `route_after_critique`: `retrieval_done` if ok or if
   `len(tried_queries) >= KNOWLEDGE_MAX_ATTEMPTS`, else `reformulate`. Node names and
   the two labels in `nodes/names.py`.
9. [x] Wire it: `get_customer → formulate_query → retrieve_knowledge →
   critique_retrieval`, then `add_conditional_edges(CRITIQUE_RETRIEVAL,
   route_after_critique, {"reformulate": FORMULATE_QUERY, "retrieval_done": TRIAGE})`.
   The back-edge is the only cycle. Check the mermaid diagram.
10. [x] Span attributes `knowledge.attempts` and `knowledge.retrieval_ok`; no query
    text. Privacy test: no query text in spans or Loki.
11. [x] Demo: `fixtures/tickets_agentic.json` (written) with a venting ticket whose
    topic the corpus covers and one question it does not (gift cards). Run it with
    `uv run ticket-classifier run fixtures/tickets_agentic.json`: per pass the console
    shows the query, then one line with best score and verdict. **Costs money: ask
    first.**

    Results (best score, top 3):

    | Ticket | Raw ticket text | First model query | Outcome at 0.65 |
    | --- | ---: | ---: | --- |
    | T-3001, venting about a double charge | 0.649 | 0.754 | ok on search 1, cites `billing.md#3` |
    | T-3002, gift cards (not covered) | 0.680 | 0.673 | ok on search 1, reply cites nothing |

    - The opening query does the rescue: the raw text of T-3001 is just below the
      threshold and would have got no passage at all.
    - T-3002 shows the weak spot: unrelated passages (accounts, billing) score 0.67
      and pass, so the score-only critique never rewords. The reply still cites
      nothing.
    - With `KNOWLEDGE_MIN_SCORE=0.7` (separate checkpoint file) T-3002 rewords twice
      (0.659, 0.699, 0.673) and stops at the bound with a reply without sources.
12. [x] Tests, offline. The `workflow_context` fixture gets an echo `write_query`
    (returns the ticket text), so call counts still see only triage and the reply.
    A scripted fake (one query per attempt) and a knowledge fake that scores per
    query drive the loop. Assert:
    - `formulate_query` records the query, and on the second pass gets the tried
      queries and the weak passages;
    - the critique passes a strong result and flags a weak one;
    - the router's three exits (ok, weak, out of tries);
    - end to end: weak then strong rewords once and triage gets the passages;
      always weak stops at `KNOWLEDGE_MAX_ATTEMPTS` with a reply without sources;
    - `write_query` falls back to the ticket text on a refusal or empty query;
    - a run that fails inside the loop continues there on the next run.
13. [x] All earlier tests pass; `make lint`, `make test`, `make test-db`. Update
    `README.md` (graph, settings, cost) and `docs/conventions.md` if a rule is new.
14. [ ] Branch and pull request. **Ask first.**

    Done: steps 1 to 10, 12 and 13. Beyond the plan: `require_context` in
    `context.py` for both nodes that need the context; `RetrievalResult.best_score`;
    `write_query` falls back on invalid output too; the scripted fake can raise, to
    test that a failed query call continues in the loop on the next run.

## Refactor: one `Retrieval` in the state

After step 14's review: the four search keys (`search_query`, `tried_queries`,
`retrieval`, `retrieval_ok`) are one immutable `Retrieval` in `models/knowledge.py`,
like `classification`. It was first called `Search`; renamed so one word,
retrieval, names the whole step (query, search, judge, reword) and "search" only
the call to the knowledge base (`KnowledgeSearch.search`).

- `queries` (tuple), `result` (latest `RetrievalResult`), `ok` (the critique's
  verdict); properties `query`, `attempts`, `passages`, `weak_passages`.
- Each node returns a new object: `with_query`, `with_result`, `judged`. A
  validator rejects steps out of order (a verdict without a result).
- No reducer: the nodes run one after another, so overwriting the whole object is
  safe; a reducer is needed only when parallel nodes write the same key. This
  differs from the exercise's `tried_queries` reducer on purpose.
- `ok` stays a stored verdict, not a property: a later model critique can say "weak"
  although a passage passed the score.
- `write_query(ticket, search)` and `query_prompt(ticket, search)` take the search;
  `RetrievalResult.split(found, min_score)` does the threshold split;
  `models.state.initial_state(ticket)` builds the initial state.
- `KnowledgePassage` and `RetrievalResult` are frozen too, with tuples. They load
  back from the checkpoint as tuples (checked in the round-trip test).
- `EscalationRequest.policies` stays a list: it is a plain dict, where msgpack loads
  a tuple back as a list.

## Expected outcome

- [x] `KNOWLEDGE_MAX_ATTEMPTS` bounds the loop.
- [x] `write_query` writes a query and rewords when told what failed (two system
      prompts).
- [x] The state has the query, the tried queries and the verdict, as one `Retrieval`
      (no reducer, see the refactor above); it starts empty.
- [x] `formulate_query` gets `write_query` injected and records the query.
- [x] `retrieve_knowledge` searches the latest query, not the raw ticket.
- [x] `critique_retrieval` is score only, deterministic, and knows when the attempts
      are spent.
- [x] `route_after_critique` loops on a weak result and moves on otherwise, bounded.
- [x] Exactly one cycle: `critique_retrieval → formulate_query` on `"reformulate"`.
- [x] The demo shows a reword and a bounded give-up (at a minimum score of 0.7).
- [x] Offline tests with an echo fake in the fixture and a scripted fake for the loop.
- [ ] Earlier tests pass; work on a branch with an open pull request.

## Open questions

- Cost: one to three query calls per ticket on top of triage and reply. Measure in
  step 11; maybe a cheaper `QUERY_MODEL`.
- Does the opening query beat the raw ticket text? `kb-eval` could compare both on
  the labelled questions (not in today's scope).
- Phase E of `plan_w9d2.md` (sentence blocks, stricter reply prompt) is still open.

## Docs

- [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Use the graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
