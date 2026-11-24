"""Shared test data; fixtures stay in conftest.py."""

from collections.abc import Sequence

import numpy as np

from ticket_classifier.models import KnowledgePassage, TicketClassification

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


class FakeKnowledge:
    """Fake knowledge base: the same passages for every query; records the queries."""

    def __init__(self, passages=(REFUND_PASSAGE,)):
        self.passages = list(passages)
        self.queries = []

    def search(self, query: str, k: int) -> list[KnowledgePassage]:
        self.queries.append((query, k))
        return self.passages[:k]
