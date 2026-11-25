"""Turn the model's answer into a ``Reply``: text with numbered citations."""

from anthropic.types import Message

from .models import Citation, KnowledgePassage, Reply

# A refusal or a cut-off answer is no reply to send.
FAILED_STOPS = ("refusal", "max_tokens", "model_context_window_exceeded")


class ReplyError(RuntimeError):
    """The model gave no usable reply, e.g. a refusal or hitting max_tokens."""


def build_reply(message: Message, passages: list[KnowledgePassage]) -> Reply:
    """Join the text blocks, put ``[n]`` after each cited one, list the sources.

    ``passages`` are the search results in request order: a citation's
    ``search_result_index`` points into them.
    """
    if message.stop_reason in FAILED_STOPS:
        raise ReplyError(f"No reply: stop reason {message.stop_reason}")

    citations: list[Citation] = []
    numbers: dict[tuple[str, int], int] = {}  # (source, ordinal) -> [n]
    parts: list[str] = []
    for block in message.content:
        if block.type != "text":
            continue
        cited: list[int] = []
        for location in block.citations or []:
            if location.type != "search_result_location":
                raise ReplyError(f"Unexpected citation type {location.type}")
            if not 0 <= location.search_result_index < len(passages):
                raise ReplyError("Citation of a search result that was not sent")
            passage = passages[location.search_result_index]
            key = (passage.source, passage.ordinal)
            if key not in numbers:
                numbers[key] = len(citations) + 1
                citations.append(
                    Citation(source=passage.source, ordinal=passage.ordinal, quotes=[])
                )
            number = numbers[key]
            citations[number - 1].quotes.append(location.cited_text)
            if number not in cited:
                cited.append(number)
        parts.append(with_markers(block.text, cited))

    text = "".join(parts).strip()
    if not text:
        raise ReplyError("No reply: the answer has no text")
    return Reply(text=text + sources_list(citations), citations=citations)


def with_markers(text: str, numbers: list[int]) -> str:
    """``[1][2]`` after the text, before its trailing whitespace."""
    if not numbers:
        return text
    stripped = text.rstrip()
    markers = "".join(f"[{number}]" for number in numbers)
    return f"{stripped} {markers}{text[len(stripped) :]}"


def sources_list(citations: list[Citation]) -> str:
    if not citations:
        return ""
    lines = [
        f"[{number}] {c.source}, part {c.ordinal}"
        for number, c in enumerate(citations, start=1)
    ]
    return "\n\nSources:\n" + "\n".join(lines)
