"""Shared test data; fixtures stay in conftest.py."""

from collections.abc import Sequence

import numpy as np
from anthropic.types import Message
from langgraph.runtime import Runtime

from ticket_classifier.config import get_settings
from ticket_classifier.context import KnowledgeSearch, QueryWriter, WorkflowContext
from ticket_classifier.knowledge import KnowledgeIndexMissingError
from ticket_classifier.models import (
    KnowledgePassage,
    Reply,
    Retrieval,
    RetrievalResult,
    Ticket,
    TicketClassification,
)

HIGH = TicketClassification(category="billing", priority="high")
LOW = TicketClassification(category="billing", priority="low")


class KeywordEmbedder:
    """Fake embedder: one dimension per known word, counted. No model, no download.

    Texts with shared keywords point the same way; others are orthogonal.
    """

    model = "fake-keyword"
    dimensions = 384

    def __init__(self, keywords=("refund", "shipping", "warranty", "password")):
        self.keywords = keywords
        self.embedded_texts = 0

    def vector(self, text: str) -> np.ndarray:
        words = text.lower().split()
        vector = np.zeros(self.dimensions, dtype=np.float32)
        for position, keyword in enumerate(self.keywords):
            vector[position] = sum(word.startswith(keyword) for word in words)
        return vector

    def embed_passages(self, texts: Sequence[str]) -> list[np.ndarray]:
        self.embedded_texts += len(texts)
        return [self.vector(text) for text in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return self.vector(text)


REFUND_PASSAGE = KnowledgePassage(
    source="refunds.md", ordinal=1, text="Refunds take 5 business days.", score=0.9
)


WEAK_PASSAGE = KnowledgePassage(
    source="shipping.md", ordinal=2, text="Parcels ship in 2 days.", score=0.3
)


def retrieval_result(
    *passages: KnowledgePassage, weak: Sequence[KnowledgePassage] = ()
) -> RetrievalResult:
    """A retrieval result as ``retrieve_knowledge`` stores it, with the configured
    minimum score."""
    return RetrievalResult(
        passages=passages,
        weak=tuple(weak),
        min_score=get_settings().knowledge_min_score,
    )


def retrieved(
    *passages: KnowledgePassage,
    weak: Sequence[KnowledgePassage] = (),
    queries: Sequence[str] = ("query",),
) -> Retrieval:
    """A retrieval after ``retrieve_knowledge``, not judged yet."""
    return Retrieval(
        queries=tuple(queries), result=retrieval_result(*passages, weak=weak)
    )


def echo_query(ticket: Ticket, retrieval: Retrieval) -> str:
    """Fake ``write_query``: the ticket text is the query."""
    return ticket.text


def runtime(
    knowledge: KnowledgeSearch, write_query: QueryWriter = echo_query
) -> Runtime[WorkflowContext]:
    """The runtime a node gets inside a run, for calling it alone."""
    return Runtime(
        context=WorkflowContext(knowledge=knowledge, write_query=write_query)
    )


class ScriptedQueries:
    """Fake ``write_query``: one answer per call, in order. An exception in the list
    is raised instead of returned. Records the retrieval each call got."""

    def __init__(self, *answers: str | Exception) -> None:
        self.answers = list(answers)
        self.calls: list[Retrieval] = []

    def __call__(self, ticket: Ticket, retrieval: Retrieval) -> str:
        self.calls.append(retrieval)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeKnowledge:
    """Fake knowledge base: the passages in ``by_query`` for a query listed there,
    else ``passages``; records the queries."""

    def __init__(self, passages=(REFUND_PASSAGE,)):
        self.passages = list(passages)
        self.by_query = {}
        self.queries = []
        self.index_missing = False

    def require_index(self) -> int:
        if self.index_missing:
            raise KnowledgeIndexMissingError("No knowledge index. Run: make kb-index")
        return 1

    def search(self, query: str, k: int) -> list[KnowledgePassage]:
        self.queries.append((query, k))
        return self.by_query.get(query, self.passages)[:k]


REPLY_TEXT = "Thanks for reaching out, the team is looking into it."
REPLY = Reply(text=REPLY_TEXT, citations=[])  # what reply_message() turns into


def reply_message(*blocks: dict, stop_reason: str = "end_turn") -> Message:
    """An API answer as ``messages.create`` returns it. A block is ``{"text": ...}``,
    optionally with ``"cited": [(search_result_index, cited_text), ...]``."""
    content = [
        {
            "type": "text",
            "text": block["text"],
            "citations": [
                {
                    "type": "search_result_location",
                    "search_result_index": index,
                    "cited_text": cited_text,
                    "source": "ignored",  # build_reply maps by index, not by source
                    "title": None,
                    "start_block_index": 0,
                    "end_block_index": 1,
                }
                for index, cited_text in block.get("cited", [])
            ]
            or None,
        }
        for block in (blocks or ({"text": REPLY_TEXT},))
    ]
    return Message.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "test",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )
