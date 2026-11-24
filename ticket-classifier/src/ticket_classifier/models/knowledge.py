"""Knowledge base data: the pieces policy documents are cut into, and search hits."""

from dataclasses import dataclass

from pydantic import BaseModel


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
    score: float  # cosine similarity: 1 same meaning, around 0.5 unrelated

    @property
    def citation(self) -> str:
        """Where the passage comes from, e.g. ``refunds.md#1``."""
        return f"{self.source}#{self.ordinal}"
