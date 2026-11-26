"""Knowledge base data: the pieces policy documents are cut into, search hits, and
labelled questions to measure the search."""

from collections.abc import Sequence
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

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    source: str
    """Document name, e.g. ``refunds.md``."""

    ordinal: int
    """Position of the chunk in its document, from 0."""

    text: str

    score: float
    """Vector search: cosine similarity, 1 same meaning, around 0.5 unrelated.
    Keyword search: ``ts_rank_cd``, from 0 up, not comparable with cosine."""

    @property
    def citation(self) -> str:
        """Where the passage comes from, e.g. ``refunds.md#1``."""
        return f"{self.source}#{self.ordinal}"


class RetrievalResult(BaseModel):
    """One search's policy passages, split at the confidence threshold."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    passages: tuple[KnowledgePassage, ...]
    """At or above ``min_score``, best first: what triage and the reply get."""

    weak: tuple[KnowledgePassage, ...]
    """Found, but below ``min_score``; shown to a reword so it can move away."""

    min_score: float
    """The threshold used: ``KNOWLEDGE_MIN_SCORE`` at search time."""

    @classmethod
    def split(cls, found: Sequence[KnowledgePassage], min_score: float) -> Self:
        """Split search hits at ``min_score``; the order of ``found`` is kept."""
        return cls(
            passages=tuple(p for p in found if p.score >= min_score),
            weak=tuple(p for p in found if p.score < min_score),
            min_score=min_score,
        )

    @property
    def has_sources(self) -> bool:
        """False: nothing passed the threshold, so the reply cites no policy."""
        return bool(self.passages)

    @property
    def dropped(self) -> int:
        """How many hits were below the threshold."""
        return len(self.weak)

    @property
    def best_score(self) -> float | None:
        """The highest score found, passed or not; None if the search found nothing."""
        return max((p.score for p in self.passages + self.weak), default=None)


class Search(BaseModel):
    """The knowledge search of one ticket: every query tried, the latest result and
    the critique's verdict on it. Immutable: each step returns a new object."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    queries: tuple[str, ...] = ()
    """Every query so far, oldest first. Its length is the number of searches."""

    result: RetrievalResult | None = None
    """The result of the latest query; None until it has been searched."""

    ok: bool | None = None
    """The critique's verdict on ``result``; None until it has been judged."""

    @model_validator(mode="after")
    def steps_in_order(self) -> Self:
        """A result needs a query, a verdict needs a result."""
        if self.result is not None and not self.queries:
            raise ValueError("a search result needs a query")
        if self.ok is not None and self.result is None:
            raise ValueError("a verdict needs a search result")
        return self

    @property
    def query(self) -> str | None:
        """The latest query, the one ``result`` belongs to."""
        return self.queries[-1] if self.queries else None

    @property
    def attempts(self) -> int:
        """Searches so far; ``KNOWLEDGE_MAX_ATTEMPTS`` bounds it."""
        return len(self.queries)

    @property
    def passages(self) -> tuple[KnowledgePassage, ...]:
        """The latest result's passages above the threshold: what triage and the
        reply get. Empty before the first search."""
        return self.result.passages if self.result else ()

    @property
    def weak_passages(self) -> tuple[KnowledgePassage, ...]:
        """The latest result's passages below the threshold, for a reword prompt."""
        return self.result.weak if self.result else ()

    def with_query(self, query: str) -> Search:
        """Start the next search. Result and verdict belonged to the previous query,
        so they are cleared."""
        return Search(queries=(*self.queries, query))

    def with_result(self, result: RetrievalResult) -> Search:
        """The latest query's result, not judged yet."""
        return Search(queries=self.queries, result=result)

    def judged(self, ok: bool) -> Search:
        """The critique's verdict on the latest result."""
        return Search(queries=self.queries, result=self.result, ok=ok)


class SearchQuery(BaseModel):
    """The model's answer when asked for a search query."""

    query: str
    """A few keywords naming the policy topic."""


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
