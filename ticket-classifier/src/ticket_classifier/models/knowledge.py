"""Knowledge base data: the pieces policy documents are cut into, search hits, and
labelled questions to measure the search."""

from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


@dataclass(frozen=True)
class Chunk:
    """One piece of a policy document. ``source`` and ``ordinal`` let us cite it."""

    source: str  # document name, e.g. "refunds.md"
    ordinal: int  # position in the document, from 0
    text: str


class KnowledgePassage(BaseModel):
    """A search hit. Pydantic, because the graph state saves it in checkpoints."""

    source: str
    ordinal: int
    text: str
    # Vector search: cosine similarity, 1 same meaning, around 0.5 unrelated.
    # Keyword search: ts_rank_cd, from 0 up, not comparable with cosine.
    score: float

    @property
    def citation(self) -> str:
        """Where the passage comes from, e.g. ``refunds.md#1``."""
        return f"{self.source}#{self.ordinal}"


class RetrievalResult(BaseModel):
    """The policy passages for one ticket, after the confidence threshold."""

    passages: list[KnowledgePassage]  # at or above min_score, best first
    min_score: float  # the threshold used, KNOWLEDGE_MIN_SCORE at retrieval time
    dropped: int  # found, but below min_score

    @property
    def has_sources(self) -> bool:
        """False: nothing passed the threshold, so the reply cites no policy."""
        return bool(self.passages)


class EvalQuestion(BaseModel):
    """A question with the document that answers it and a phrase of the answer.

    Labelled by phrase, not by chunk, so it stays valid for any chunk setting.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    question: str
    source: str | None  # None: the knowledge base cannot answer it
    answer: str | None  # a phrase of the answering passage, as in the document

    @model_validator(mode="after")
    def source_and_answer_together(self) -> Self:
        if (self.source is None) != (self.answer is None):
            raise ValueError("source and answer must both be set or both be null")
        return self

    @property
    def answerable(self) -> bool:
        return self.source is not None
