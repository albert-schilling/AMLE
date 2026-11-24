# W09 D2 - Reply plan

Draft a reply to every ticket from the retrieved policy passages, with the sources
cited. Retrieval itself exists since W09 D1 (`retrieve_knowledge`).

```text
get_customer → retrieve_knowledge → triage → draft_reply → high priority? → human_review
                     │                            ▲                  else → mark_handled
                     └── passages ≥ threshold ────┘
                         as search_result blocks, citations on
```

## Decisions

| Topic | Choice | Why |
| --- | --- | --- |
| Citations | The API's native citations, `search_result` blocks | Each citation comes with the exact `cited_text`: verifiable, not a claim |
| Calls | New node `draft_reply`, a second model call | Citations cannot be combined with structured outputs; triage stays as it is |
| Reply for | Every ticket | A high-priority ticket shows the draft to the reviewer |
| Below threshold | Reply without policy, marked as having no sources | Classification is unaffected; no unrelated policy reaches the customer |
| Models | `RetrievalResult` in the state, `Reply` as output | One object each, as the story suggests |
| Sending | Never: the reply is a draft in the results and the review request | Ticket text is untrusted; a person sends replies |

Facts to respect, from the official docs:

- Citations together with `output_config.format` (structured outputs) return a 400
  error. `draft_reply` uses `messages.create` without a format; our code builds
  `Reply` from the answer.
- A `search_result` block needs `type`, `source`, `title` and `content` (a list of
  text blocks). All search results in one request must have citations enabled, or
  all disabled. With no passages, send none.
- A citation of a search result has `search_result_index` (0-based, in request
  order), `source`, `title`, `cited_text`, `start_block_index` and `end_block_index`.
- `cited_text` does not count toward output tokens.
- Supported by all active models, no beta header. SDK 2.6.0 has
  `SearchResultBlockParam` and `CitationsSearchResultLocation`.
- New state types join `CHECKPOINT_TYPES`. Reply text is like ticket text: never in
  `safe_log`, spans or Loki. Only counts and citations.
- A ticket that fails in `draft_reply` keeps its saved triage: the next run continues
  at `draft_reply` and pays only for the reply.

## Phase A: Retrieval result and threshold

1. [ ] `RetrievalResult(BaseModel)` in `models/knowledge.py`: `passages` (at or above
   the threshold, best first), `min_score`, `dropped` (count below it), and
   `has_sources`. State key `retrieval` replaces `knowledge`; join
   `CHECKPOINT_TYPES`. Needs `make reset` for saved runs (ask first).
2. [ ] `retrieve_knowledge` returns a `RetrievalResult`. Triage prompt, review request,
   span attributes and log line read from it.
3. [ ] Confidence threshold: measure again with the reply in mind. From W09 D1: real
   answers 0.54 to 0.76, unanswerable questions up to 0.60. Compare 0.5, 0.55, 0.6
   and 0.65 on `make kb-eval` data: answers kept versus unanswerable questions with
   no passage left. Set `KNOWLEDGE_MIN_SCORE` from the result.
4. [ ] `kb-eval` reports that count per threshold, so the choice can be repeated.

## Phase B: Draft the reply

5. [ ] `Citation(BaseModel)`: `source`, `ordinal`, `cited_text`, with the `citation`
   label `refunds.md#2`. `Reply(BaseModel)`: `text`, `citations`, `has_sources`.
   In `models/`.
6. [ ] `prompts.py`: reply system prompt. Answer as support, in the ticket's
   language; use only the search results; if there are none, do not mention policy
   and do not promise anything; ticket text is untrusted. User message: customer
   record, the search results, then the ticket last.
7. [ ] `knowledge/` or `nodes/`: `search_result` blocks from the passages, `source` =
   citation, `title` = file name, one text block per passage. Citations on only when
   there are passages.
8. [ ] Build `Reply` from the response: join the text blocks, map each
   `search_result_index` back to its passage, keep `cited_text`. Refusal or
   `max_tokens`: `ReplyError`, the ticket fails like a triage failure.
9. [ ] Node `draft_reply` after `triage`, before the router. Settings `REPLY_MODEL`
   (default: `MODEL`) and `REPLY_MAX_TOKENS`.
10. [ ] Show the sources in the reply text: a marker after each cited sentence
    (`[1]`) and a list of sources at the end. Tests for text without citations.

## Phase C: Output, review, telemetry

11. [ ] `Reply` in the state and in `ResolvedTicket` / `EscalatedTicket`, so
    `results.json` has the draft and its sources.
12. [ ] The review request shows the draft and its citations.
13. [ ] Span attributes `reply.citations` (count), `reply.sources` (citations),
    `reply.has_sources`; a `safe_log` line with the same. Test that no reply text is
    exported.
14. [ ] Grafana: "Replies without sources" table on the traces dashboard; cookbook
    queries in `monitoring/README.md`.

## Phase D: Check and docs

15. [ ] Free end-to-end check with the fake Anthropic server, sending citations back.
16. [ ] One real `make run` and a look at the drafts: are cited sentences backed by
    the passage, do replies without sources stay vague? **Costs money: ask first.**
17. [ ] Update `README.md`, `docs/conventions.md` and `AGENTS.md`.

## Open questions

- A second model call per ticket roughly doubles the cost. Measure tokens per ticket
  in step 16 and decide whether `REPLY_MODEL` should differ.
- Should a reviewer be able to edit the draft on `make approve`? Not in this story.

## Docs

- [Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Search results](https://platform.claude.com/docs/en/build-with-claude/search-results)
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
