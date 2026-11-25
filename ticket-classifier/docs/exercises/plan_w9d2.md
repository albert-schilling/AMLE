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

1. [x] `RetrievalResult(BaseModel)` in `models/knowledge.py`: `passages` (at or above
   the threshold, best first), `min_score`, `dropped` (count below it), and
   `has_sources`. State key `retrieval`; join `CHECKPOINT_TYPES`.
2. [x] `retrieve_knowledge` returns a `RetrievalResult`. Triage prompt, review request,
   span attributes and log line read from it.
3. [x] Confidence threshold: measure again with the reply in mind. From W09 D1: real
   answers 0.54 to 0.76, unanswerable questions up to 0.60. Compare 0.5, 0.55, 0.6
   and 0.65 on `make kb-eval` data: answers kept versus unanswerable questions with
   no passage left. Set `KNOWLEDGE_MIN_SCORE` from the result.

   Six more unanswerable questions (Q-17 to Q-22: PayPal, loyalty program, student
   discount, address change, headquarters, gift cards), so 14 answerable and 8 not.
   On 60/20, top 3 per question:

   | Min score | Answer kept | Answerable, no passage | Unanswerable, no passage |
   | ---: | ---: | ---: | ---: |
   | 0.50 | 0.93 | 0.00 | 0.00 |
   | 0.55 | 0.86 | 0.00 | 0.25 |
   | 0.60 | 0.86 | 0.00 | 0.38 |
   | 0.62 | 0.86 | 0.07 | 0.75 |
   | 0.65 | 0.86 | 0.14 | 0.88 |
   | 0.68 | 0.71 | 0.21 | 0.88 |
   | 0.70 | 0.64 | 0.29 | 0.88 |

   - `KNOWLEDGE_MIN_SCORE=0.65`. Up to 0.65 only the spilled coffee answer (0.54) is
     lost; above it real answers go.
   - The two answerable questions without a passage at 0.65 (blender, coffee) had no
     answer in their top 3 anyway: a reply without sources is better than a wrong one.
   - Of the fixture tickets, the CSV export ticket (best 0.62) gets no policy.
   - 22 questions are few: one question moves a share by 0.07 or 0.13.
4. [x] `kb-eval` reports that count per threshold, so the choice can be repeated.

## Phase B: Draft the reply

5. [x] `Citation(BaseModel)`: `source`, `ordinal`, `cited_text`, with the `citation`
   label `refunds.md#2`. `Reply(BaseModel)`: `text`, `citations`, `has_sources`.
   In `models/`.

   One `Citation` per passage, with `quotes` (every `cited_text` from it), so a
   passage cited twice keeps one number.
6. [x] `prompts.py`: reply system prompt. Answer as support, in the ticket's
   language; use only the search results; if there are none, do not mention policy
   and do not promise anything; ticket text is untrusted. User message: customer
   record, the search results, then the ticket last.
7. [x] `knowledge/` or `nodes/`: `search_result` blocks from the passages, `source` =
   citation, `title` = file name, one text block per passage. Citations on only when
   there are passages.
8. [x] Build `Reply` from the response: join the text blocks, map each
   `search_result_index` back to its passage, keep `cited_text`. Refusal or
   `max_tokens`: `ReplyError`, the ticket fails like a triage failure.
9. [x] Node `draft_reply` after `triage`, before the router. Settings `REPLY_MODEL`
   (default: `MODEL`) and `REPLY_MAX_TOKENS`.
10. [x] Show the sources in the reply text: a marker after each cited sentence
    (`[1]`) and a list of sources at the end. Tests for text without citations.

    Done in Phase B: `replies.build_reply` (markers, source list, `ReplyError` on
    refusal, `max_tokens`, empty text or a citation of a result not sent),
    `nodes/draft_reply.py`, `REPLY_SYSTEM_PROMPT` and `reply_content` in `prompts.py`.
    The router `route_by_priority` follows `draft_reply`. A failed reply fails
    the ticket; the next run continues at `draft_reply` (tested).

## Phase C: Output, review, telemetry

11. [x] `Reply` in the state and in `ResolvedTicket` / `EscalatedTicket`, so
    `results.json` has the draft and its sources.
12. [x] The review request shows the draft and its citations.
13. [x] Span attributes `reply.citations` (count), `reply.sources` (citations),
    `reply.has_sources`; a `safe_log` line with the same. Test that no reply text is
    exported.
14. [x] Grafana: "Replies without sources" table on the traces dashboard; cookbook
    queries in `monitoring/README.md`.

    Done in Phase C: `reply` is a required field of every result row. The review
    request has `reply`. The safe log line is the one from `draft_reply`. The weak
    matches box defaults to 0.7: with a minimum of 0.65, no passage below 0.65
    reaches the span.

## Phase D: Check and docs

15. [x] Free end-to-end check with the fake Anthropic server, sending citations back.
    Covered by step 16: the real run checked the request and the citation answer.
16. [x] One real `make run` and a look at the drafts: are cited sentences backed by
    the passage, do replies without sources stay vague? **Costs money: ask first.**

    First run: no ticket failed, so the request shape and the citation answer work
    with the real API. 5 of 8 replies cite one passage (T-2004 and T-2005 quote
    `billing.md#4` twice). T-1001, T-1002 and T-2002 have no sources.

    Drafts read: every cited sentence is backed by its passage, and unrelated
    passages above the threshold (T-2002) are not cited. But replies promise things
    no source states, and quotes are whole passages. Fixes in Phase E.
17. [x] Update `README.md`, `docs/conventions.md` and `AGENTS.md`.

## Phase E: Optimization

Findings from the drafts of step 16, worst first:

- T-1004 promises a call from billing specialists "today", while the ticket waits
  for a human decision.
- Made-up timing: "a day or two" (T-2001; the policy says a few business days),
  "right away" (T-2005), "shortly" (T-1001).
- T-1001 states a policy from `billing.md#0` without citing it.
- `cited_text` is always the whole passage: one text block per passage can only be
  cited as a whole. T-2004 and T-2005 hold the same quote twice.
- Chunks end mid-sentence: `billing.md#3` stops before "within a few business
  days" and "refunded in full", which are in `#4`.

18. [ ] One text block per sentence in each `search_result` block, so
    `cited_text` is the cited sentence. Test the split.
19. [ ] Stricter reply prompt: no timeframes, callbacks or escalation promises
    unless a source states them; cite every policy statement; for high priority,
    say only that a person will review the ticket.
20. [ ] Drop duplicate quotes in `build_reply`, if step 18 does not make them
    impossible.
21. [ ] Chunks that end at sentence boundaries (W09 D1 chunker), then
    `make kb-index` and `make kb-eval` again; check the threshold still holds.
22. [ ] One more `make run` and read the drafts against the findings above.
    **Costs money: ask first.**

## Open questions

- A second model call per ticket roughly doubles the cost. Measure tokens per ticket
  in step 16 and decide whether `REPLY_MODEL` should differ.
- Should a reviewer be able to edit the draft on `make approve`? Not in this story.

## Docs

- [Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Search results](https://platform.claude.com/docs/en/build-with-claude/search-results)
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
