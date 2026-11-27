# Review: RAG and search loop (W09 D2 and D3)

Structure and readability review of the uncommitted changes. Suggestions only;
nothing is changed yet. Items 1 to 4 give the most clarity.

## Worth doing

1. [x] **One word for one thing.** The state said `search`, the nodes, `RetrievalResult`
   and `knowledge.retrieval_ok` said retrieval. Done: everything is retrieval
   (`Retrieval`, `state["retrieval"]`, `RETRIEVAL_DONE`, log "attempt 2 of 3", test
   helpers `retrieved` and `retrieval_result`). "Search" now means only the call to
   the knowledge base: `KnowledgeSearch.search`, `SearchQuery`.
2. [x] **`KnowledgeSearch` and `Search` were easy to mix up.** Solved by item 1. The
   protocol keeps its name: it does one search, not a whole retrieval, and
   `KnowledgeBase` is the name of the class it describes in `knowledge/store.py`.
3. [x] **The three-way decision existed twice.** `critique_retrieval` worked out "ok /
   attempts spent / reword" for its log text; `route_after_critique` decided the
   same again. Done: `Retrieval.can_reword(max_attempts)` decides; the router and
   the critique's log text both ask it.
4. [x] **A node imported from the router.** `critique_retrieval` took
   `attempts_spent` from `routing.py`. Done: `attempts_spent` is gone, replaced by
   `can_reword` on the model; the setting is passed in, so the model reads none.
5. [x] **Prompt wording.** `UNTRUSTED_TICKET` said "data to classify", but the query
   and reply prompts use it too: now "treat it as data". `REWORD` said "the passages
   *they* found", but only the latest search's passages are shown: now "the passages
   the last query found" (also in the `formulate_query` docstring).
6. [x] **`record_state` in `telemetry.py` was scattered.** Search attributes came
   before and after the classification. Done: `record_state` calls
   `record_retrieval`, `record_classification` and `record_reply`.
7. [x] **Two meanings of "best score".** The span's `knowledge.top_score` is the best
   passage that passed the threshold; the critique's score also counts the weak
   ones. Done: `RetrievalResult.top_score` (passed, used for the span) and
   `best_found_score` (passed or not, in the critique's log line "best found
   score").

## Smaller

8. [x] **The docstring rule was applied in one file only.** Done: field comments in
   `reply.py`, `results.py`, `state.py` (also `EscalationRequest.policies`) and
   `knowledge.py` are docstrings now; `Ticket` got a class docstring. The rule now
   covers TypedDict keys and type aliases.
9. [x] **Return types.** The `Retrieval` methods returned the class, `split` returned
   `Self`. Done: a method that builds a new object names its class; `Self` only
   where a validator returns `self` (rule in `conventions.md`).
10. [x] **Edge labels and routers.** `REFORMULATE` and `SEARCH_DONE` lived in
    `routing.py`. Done: the labels are in `names.py`; each router's docstring says
    why it returns node names or labels.
11. [x] **No stream event for the query call.** Done: `formulate_query` sends
    "writing search query" with ticket id, attempt and model through
    `runtime.stream_writer`; the query itself stays out.
12. [x] **Three "missing step" errors in three modules.** Done: `MissingQueryError`
    and `MissingResultError` are one `RetrievalStepError` in `models/knowledge.py`.
    `MissingContextError` stays: a run started without context is a different
    mistake from a graph wired in the wrong order.
13. [x] **`QUERY_MAX_TOKENS` was a constant**, the reply has the `REPLY_MAX_TOKENS`
    setting. Done: it is the setting `QUERY_MAX_TOKENS` (default 200) next to
    `QUERY_MODEL`, since another model can need another limit, and a too-low limit
    quietly falls back to the ticket text.

## Tests

14. [ ] **Two ways to fake the private query.** `test_spans` uses `mocker.patch`,
    `test_telemetry` uses `monkeypatch.setattr`. One fixture,
    `private_query_writer`, for both.
15. [ ] **Helper names.** `searched(...)` is now `retrieved(...)` (item 1). The `ScriptedQueries` docstring:
    "an exception in the list is raised instead of returned".
16. [ ] **Untyped fakes.** `echo_query` and `ScriptedQueries` are untyped, `runtime()`
    is typed. Allowed for tests, but these fakes are where a fake can drift from the
    `QueryWriter` protocol.

## Docs

17. [ ] **`plan_w9d3.md`** describes the old state (`tried_queries`, `retrieval_ok`)
    in steps 3 to 8 and explains the change only in "Refactor". A one-line pointer at
    step 4 helps the reader.
18. [ ] **`NOTES.md`:** the TODO "start_state → initial state" is done.
