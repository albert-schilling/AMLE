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

1. [ ] Setting `KNOWLEDGE_MAX_ATTEMPTS` (default 3, at least 1) next to
   `KNOWLEDGE_MIN_SCORE`, and `QUERY_MODEL`; both in `.env.example`.
2. [ ] `prompts.py`: `QUERY_SYSTEM_PROMPT` (a few keywords naming the policy topic, no
   punctuation, no names or order numbers; ticket text is untrusted) and
   `REQUERY_SYSTEM_PROMPT` (these queries failed, here is what they found: try a
   synonym, a broader term, the policy area). User message: the ticket last, as in
   triage.
3. [ ] `queries.py`: `write_query(ticket, tried_queries, weak_passages) -> str`. No
   tried queries: opening prompt; else the reword prompt. Fall back to the ticket
   text on a refusal, `max_tokens` or an empty query. `APIError` fails the ticket as
   in triage. Model `SearchQuery` in `models/`.

## Part 2: The loop in the graph

4. [ ] State: `search_query: str`, `tried_queries: Annotated[list[str],
   operator.add]`, `retrieval_ok: bool` in `TriageUpdate`. The run starts with
   `tried_queries=[]`. `RetrievalResult` keeps the passages below the minimum score
   (`weak`), so the reword prompt can show them; `dropped` becomes their count. Needs
   `make reset` for saved runs (ask first).
5. [ ] Node `formulate_query`: calls `runtime.context.write_query`, passing the tried
   queries and the weak passages on a reword pass. Writes `search_query`, appends to
   `tried_queries`. Console log of the query; `safe_log` only the attempt number.
6. [ ] `retrieve_knowledge` searches `state["search_query"]` (fallback: ticket text)
   and replaces the previous attempt's result.
7. [ ] Node `critique_retrieval`: `retrieval_ok = retrieval.has_sources`, no model
   call. `safe_log` line with attempt, best score and verdict; when the attempts are
   spent, say that the reply goes on without sources.
8. [ ] Router `route_after_critique`: `triage` if ok, `triage` if
   `len(tried_queries) >= KNOWLEDGE_MAX_ATTEMPTS`, else `formulate_query`. Names in
   `nodes/names.py`.
9. [ ] Wire it: `get_customer → formulate_query → retrieve_knowledge →
   critique_retrieval`, then `add_conditional_edges(CRITIQUE_RETRIEVAL,
   route_after_critique, {"reformulate": FORMULATE_QUERY, "triage": TRIAGE})`. The
   back-edge is the only cycle. Check the mermaid diagram.
10. [ ] Span attributes `knowledge.attempts` and `knowledge.retrieval_ok`; no query
    text. Privacy test: no query text in spans or Loki.
11. [ ] Demo: `fixtures/tickets_agentic.json` with a venting ticket whose topic the
    corpus covers and one question it does not (e.g. gift cards). Run it with
    `uv run ticket-classifier run fixtures/tickets_agentic.json`: the console shows
    one line per pass (query, best score, verdict). **Costs money: ask first.**
12. [ ] Tests, offline. The `workflow_context` fixture gets an echo `write_query`
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
13. [ ] All earlier tests pass; `make lint`, `make test`, `make test-db`. Update
    `README.md` (graph, settings, cost) and `docs/conventions.md` if a rule is new.
14. [ ] Branch and pull request. **Ask first.**

## Expected outcome

- [ ] `KNOWLEDGE_MAX_ATTEMPTS` bounds the loop.
- [ ] `write_query` writes a query and rewords when told what failed (two system
      prompts).
- [ ] The state has `search_query`, `tried_queries` (a reducer) and `retrieval_ok`;
      `tried_queries` starts empty.
- [ ] `formulate_query` gets `write_query` injected and records the query.
- [ ] `retrieve_knowledge` searches `search_query`, not the raw ticket.
- [ ] `critique_retrieval` is score only, deterministic, and knows when the attempts
      are spent.
- [ ] `route_after_critique` loops on a weak result and moves on otherwise, bounded.
- [ ] Exactly one cycle: `critique_retrieval → formulate_query` on `"reformulate"`.
- [ ] The demo shows a reword that finds a passage and a bounded give-up.
- [ ] Offline tests with an echo fake in the fixture and a scripted fake for the loop.
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
