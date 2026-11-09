"""Core model calls: triage (one tool call, one schema, no regex) and a streamed draft reply.

Deliberately simple/direct (talks to the real Anthropic SDK, no injected client
abstraction) - see tests/test_triage.py for how we verify this offline anyway, by patching
the SDK boundary (`scoutbot.core._client`) directly in the test rather than building a
mockable interface into the production code.

Note: this lives in `core.py`, not `triage.py` - the public function is called `triage()`
(see `scoutbot/__init__.py`), and a module can't share its submodule-attribute name with a
function re-exported from that submodule (it shadows the submodule reference, which breaks
`mock.patch("scoutbot.triage._client")`-style patching). Keep the module and the function name
distinct.
"""
import os
from typing import Callable, Optional, Sequence

from anthropic import Anthropic

from .schema import QueryRoute, TicketTriage

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

TRIAGE_TOOL = {
    "name": "triage_ticket",
    "description": "Record the triage decision for a single support ticket.",
    "input_schema": TicketTriage.model_json_schema(),
}


class TriageError(RuntimeError):
    """Raised when the model's reply can't be turned into a valid TicketTriage, even after a
    retry. Loud and specific beats a silent, wrong guess."""


def _client() -> Anthropic:
    # Reads ANTHROPIC_API_KEY from the environment - never hardcode it (that was Jonas's bug).
    return Anthropic()


def _request_triage(ticket_text: str) -> TicketTriage:
    response = _client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system="You triage support tickets by calling triage_ticket exactly once.",
        messages=[{"role": "user", "content": ticket_text}],
        tools=[TRIAGE_TOOL],
        tool_choice={"type": "tool", "name": "triage_ticket"},
    )
    tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
    if not tool_use_blocks:
        raise TriageError("Model did not call triage_ticket.")
    # Unlike OpenAI's function-call arguments (a JSON string you have to json.loads), Anthropic
    # hands back `.input` already parsed into a dict - no json.loads needed here.
    return TicketTriage.model_validate(tool_use_blocks[0].input)


def triage(ticket_text: str) -> TicketTriage:
    """Classify one support ticket.

    Retries once on any failure (malformed input, schema mismatch, no tool call) and then
    raises TriageError - see Topic 2, slide 14: "retry once, then escalate, don't silently
    guess." A production version would likely narrow the caught exceptions further; kept broad
    here to keep the retry policy easy to read for teaching purposes.
    """
    try:
        return _request_triage(ticket_text)
    except Exception:
        try:
            return _request_triage(ticket_text)
        except Exception as exc:
            raise TriageError(f"triage() failed twice for ticket: {ticket_text!r}") from exc


ROUTER_SYSTEM = (
    "You are a router for a customer-support assistant that has a policy knowledge base. "
    "Decide how much retrieval a ticket needs and answer with exactly one word:\n"
    "- direct: the ticket needs no policy lookup at all - a greeting, a thank-you, an "
    "acknowledgement ('that's all, thanks'), or small talk that courtesy alone answers.\n"
    "- retrieve: a clear, single-topic policy question that one good search can answer, like "
    "'how long do refunds take?' or 'is shipping free over fifty euros?'.\n"
    "- iterative: anything vague, multi-part, oblique, or specific to this customer's account, "
    "where the first search might miss and the assistant should be able to reword and search "
    "again.\n"
    "Answer with only one of these words: direct, retrieve, iterative. When you are unsure, "
    "answer iterative - it is always safe to search harder, never safe to skip retrieval on a real "
    "question."
)
"""System prompt for the query router: how hard should the agent work to answer this ticket?

Day 4's one new model call, and the smallest one in the graph - a single word out. It is the
adaptive-RAG decision: not every ticket earns the full re-query loop, so a cheap classifier picks a
strategy and the graph routes on it. The prompt spells out the three strategies and, crucially, names
the safe default: an unsure router should retrieve *more*, because skipping retrieval on a real
question is the ungrounded guess the whole week exists to prevent.
"""


def _route_label(response) -> str:
    """Pull one of the three route words out of the router's reply, defaulting to the safe one.

    The model is asked for a bare label, but a stray "iterative." or "route: retrieve" should not
    break routing, so this scans the reply for the first known route word rather than demanding an
    exact match. The three values do not overlap as substrings, so a contains-check is unambiguous.
    Anything unrecognisable falls back to `iterative`, the same safe default the prompt asks for:
    the router failing should mean *more* retrieval, never a skipped search.
    """
    parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
    word = " ".join(parts).strip().lower()
    for route in QueryRoute:
        if route.value in word:
            return route.value
    return QueryRoute.iterative.value


def classify_query(ticket_text: str) -> str:
    """Classify a ticket into a retrieval strategy: `direct`, `retrieve`, or `iterative`.

    The whole of Day 4's first idea, in one model call. It reads the ticket and returns how much
    retrieval it deserves - none, one search, or the full bounded loop - and the graph takes a
    different path for each. That is *adaptive* RAG: the effort is matched to the question instead of
    every ticket paying for the same loop.

    Deliberately the cheapest call in the graph: `max_tokens=16`, a single word out, no tool schema.
    Like `triage` and `formulate_query` it goes through the same `_client()` boundary the tests patch,
    so nothing here reaches the network in the suite. `_route_label` guarantees the return is always
    one of the three valid values, so callers never have to validate it again.
    """
    response = _client().messages.create(
        model=MODEL,
        max_tokens=16,
        system=ROUTER_SYSTEM,
        messages=[{"role": "user", "content": f"Ticket:\n{ticket_text}"}],
    )
    return _route_label(response)


QUERY_SYSTEM = (
    "You turn a customer support ticket into a short search query for a policy knowledge "
    "base. Return only the query, a handful of keywords or a short phrase naming the policy "
    "topic the customer is really asking about. No punctuation, no explanation, no quotes. "
    "A ticket about a late refund becomes something like: refund processing time."
)
"""System prompt for the agent's own search query, the input to the retrieval 'tool'.

Day 3's shift is that the query is now the model's decision, not the raw ticket text. A ticket is a
person venting; a good query is the policy topic underneath it. Naming that topic is a small model
call, and it is what makes retrieval *agentic* rather than automatic: the agent chooses what to look
up, and can choose differently when the first look-up comes back weak.
"""

REQUERY_SYSTEM = (
    "You are rewriting a policy-knowledge-base search query that did not find a good answer. "
    "You are given the ticket, the queries already tried, and the weak passages they returned. "
    "Return only a single new query, worded differently from the ones already tried, that might "
    "surface a better passage. A handful of keywords or a short phrase. No punctuation, no "
    "explanation, no quotes. Try a synonym, a broader term, or the specific policy area."
)
"""System prompt for a *re-query*: the same job as `QUERY_SYSTEM`, but told what already failed.

This is the self-correcting half of the loop. A first query that scored below the confidence floor
is not a dead end; it is evidence. Handing the model the tried queries and the passages they pulled
lets it move to a different phrasing rather than repeat itself, which is the whole point of trying
again instead of giving up or guessing.
"""


def _query_text(response) -> str:
    """Pull the plain-text query out of a `messages.create` response, first line only."""
    parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
    return " ".join(parts).strip().splitlines()[0].strip() if parts else ""


def formulate_query(
    ticket_text: str,
    tried_queries: Sequence[str] = (),
    weak_passages: str = "",
) -> str:
    """Turn a ticket into a knowledge-base search query, and reword it when the last one missed.

    One function, two moods, chosen by whether anything was tried before. With no `tried_queries`
    this is the agent's opening move: read the ticket, name the policy topic, return a focused query
    (`QUERY_SYSTEM`). With `tried_queries` and the `weak_passages` they returned, it is a re-query:
    the model is told what already failed and asked for a different phrasing (`REQUERY_SYSTEM`). That
    is the model driving retrieval, which is what "retrieval as a tool" means here: the tool is
    `KnowledgeBase.search`, and its input is a decision the agent makes and can revise.

    Deliberately a plain, non-streamed `messages.create` returning a short string, patched in tests at
    the same `scoutbot.core._client` boundary as `triage()` and `stream_reply()`, so nothing here
    reaches the network in the suite. Falls back to the ticket text if the model returns nothing
    usable, because an empty query is worse than a blunt one.
    """
    if tried_queries:
        user = (
            f"Ticket:\n{ticket_text}\n\n"
            f"Queries already tried: {', '.join(tried_queries)}\n\n"
            f"Weak passages they returned:\n{weak_passages or '(nothing useful)'}"
        )
        system = REQUERY_SYSTEM
    else:
        user = f"Ticket:\n{ticket_text}"
        system = QUERY_SYSTEM
    response = _client().messages.create(
        model=MODEL,
        max_tokens=64,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return _query_text(response) or ticket_text


DRAFT_SYSTEM = (
    "You draft short replies to customer support tickets, for a human to review before "
    "sending. Three or four sentences. Acknowledge the problem, say what happens next, "
    "and promise nothing you weren't told. No greeting or sign-off boilerplate."
)

GROUNDED_DRAFT_SYSTEM = (
    "You draft short replies to customer support tickets, for a human to review before "
    "sending. Three or four sentences. Acknowledge the problem, say what happens next, and "
    "no greeting or sign-off boilerplate.\n\n"
    "You are given the only policy passages you may rely on, each tagged with its source in "
    "square brackets. Ground every factual claim about our policy in those passages and cite "
    "the source you used in brackets, like [refunds], right where you use it. Do not add "
    "numbers, timeframes or promises that are not in the passages. If the passages do not "
    "answer the question, say a teammate will follow up rather than inventing an answer, and "
    "do not cite anything."
)
"""The system prompt for a *grounded* draft: answer from the passages, cite them, refuse to guess.

This is the whole of Day 2's first idea. `DRAFT_SYSTEM` let the model say whatever sounded right;
this one hands it the retrieved policy passages as the *only* thing it may lean on, tells it to cite
which one, and tells it what to do when they do not cover the question. The refusal clause matters as
much as the citation one: a bot that invents a refund window when retrieval misses is worse than one
that says a teammate will follow up, because the confident wrong answer is the one nobody catches.
"""


def _passages_block(knowledge: str) -> str:
    """Wrap the retrieved passages in a labelled block, or return empty when there are none."""
    return f"Policy passages you may cite:\n{knowledge}" if knowledge.strip() else ""


def _memory_block(memory: str) -> str:
    """Wrap recalled memories in a labelled block that tells the model to use, not cite, them.

    Deliberately different wording from `_passages_block`. Policy passages are a *source* the model must
    cite; memories are *background* about the customer that should shape the reply's tone and continuity
    without being quoted or cited. The label says so, so a recalled "asked about this last week" makes the
    answer feel like a continuation rather than turning into a fake citation.
    """
    if not memory.strip():
        return ""
    return (
        "What you already know about this customer from past tickets "
        "(use for context and continuity, do not cite):\n" + memory
    )


def stream_reply(
    ticket_text: str,
    on_chunk: Optional[Callable[[str], None]] = None,
    context: str = "",
    knowledge: str = "",
    memory: str = "",
) -> str:
    """Draft a reply, handing each piece of text to `on_chunk` as the model produces it.

    The important word is *as*. `messages.stream()` is a context manager over an incremental
    response, so text is available seconds before the reply is finished, and this function
    passes each piece straight out through the callback instead of holding it. The full text
    is still returned at the end, because the graph node needs to put it in state.

    The callback is what lets a caller decide where the text goes without this function
    knowing: `graph.draft_reply_node` sends it into LangGraph's stream, a test collects it in
    a list, and a plain script could print it. Passing `None` just accumulates silently.

    One honest note for teaching, measured rather than assumed: the pieces are *not* single
    tokens. Anthropic decides the granularity, and in practice a reply of this length arrives
    in roughly ten to twenty chunks of a phrase or two each, over three to five seconds, with
    the first one landing under a second in. The point is not per-token granularity, it is
    that output exists while the call is still in flight.

    **`knowledge` is Day 2's addition, and it changes the reply from recalled to grounded.** When
    it is empty this is exactly the Week 8 draft: the ungrounded `DRAFT_SYSTEM`, and a prompt of just
    the ticket and its triage context. When it carries retrieved passages, the system prompt switches
    to `GROUNDED_DRAFT_SYSTEM` and the passages go into the user message as the only material the
    model may cite. Nothing else about the call changes, which is the point worth making to students:
    "RAG" here is not a framework or a new API, it is retrieved text placed in the prompt plus an
    instruction to use only that text and to cite it.

    **`memory` is Day 5's addition, and it is deliberately not like `knowledge`.** When it carries
    recalled past-ticket lines they go into the prompt as *background* about this customer, under a label
    that tells the model to use them for continuity but not to cite them. It does not switch the system
    prompt and it does not turn an ungrounded reply grounded: a `direct` "thanks!" from a known customer
    can still read warmly without any policy passage in sight. Memory personalises; knowledge grounds;
    the prompt can carry either, both, or neither, and the two never get confused because only one is
    ever presented as a citable source.

    The same `_client()` boundary as `triage()`, so tests patch `scoutbot.core._client` and
    never touch the network.
    """
    pieces = []
    grounded = bool(knowledge.strip())
    prompt = "\n\n".join(
        part
        for part in (ticket_text, context, _memory_block(memory), _passages_block(knowledge))
        if part.strip()
    )
    with _client().messages.stream(
        model=MODEL,
        max_tokens=512,
        system=GROUNDED_DRAFT_SYSTEM if grounded else DRAFT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            pieces.append(text)
            if on_chunk is not None:
                on_chunk(text)
    return "".join(pieces)
