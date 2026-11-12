# User story 3.1: trying out web_search (plan, not implemented)

Related story: [user_story_3.md](user_story_3.md)

## Tool facts

- Server-side tool: Anthropic runs the search. Results always come with citations.
- Settings: `max_uses`, `allowed_domains` or `blocked_domains` (not both), `user_location`.
- Use `web_search_20250305`. Newer versions add dynamic filtering via code execution, which we do not need.
- Cost: $10 per 1,000 searches plus tokens. Supported by Haiku 4.5 and 5.5.
- Search returns index snippets, not the live page, so it is weaker than fetch for an outage check.

## Idea

Search finds the status page, fetch reads it. Use a ticket without the Mollie URL (for example
T-2003: "check whether Mollie has an outage"). URLs from search results count as allowed
sources for web fetch.

## Plan

1. Setting `WEB_SEARCH_ENABLED`, default off. The URL-in-ticket setup stays the main path.
2. `make_web_search_tool()` in `tools.py`: `max_uses: 3`, `allowed_domains: ["status.mollie.com"]`.
3. Trace `web_search_tool_result` in `trace.py` (result list or error code).
4. Add ticket T-2003 without URL, plus tests for guardrails and trace.
5. Run T-2003 about 10 times on `claude-haiku-5-5`. Count: searched, fetched, found the real status page.
6. Note the result here.

## Risks

- A domain-restricted search may find nothing useful if the status page is poorly indexed.
- Search plus fetch adds more skipped-tool flakiness (see [user_story_3_flaky_fetch.md](user_story_3_flaky_fetch.md)).
