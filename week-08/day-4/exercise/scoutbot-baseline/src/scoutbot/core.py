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
from typing import Callable, Optional

from anthropic import Anthropic

from .schema import TicketTriage

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


DRAFT_SYSTEM = (
    "You draft short replies to customer support tickets, for a human to review before "
    "sending. Three or four sentences. Acknowledge the problem, say what happens next, "
    "and promise nothing you weren't told. No greeting or sign-off boilerplate."
)


def stream_reply(
    ticket_text: str,
    on_chunk: Optional[Callable[[str], None]] = None,
    context: str = "",
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

    The same `_client()` boundary as `triage()`, so tests patch `scoutbot.core._client` and
    never touch the network.
    """
    pieces = []
    prompt = f"{ticket_text}\n\n{context}".strip()
    with _client().messages.stream(
        model=MODEL,
        max_tokens=512,
        system=DRAFT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            pieces.append(text)
            if on_chunk is not None:
                on_chunk(text)
    return "".join(pieces)
