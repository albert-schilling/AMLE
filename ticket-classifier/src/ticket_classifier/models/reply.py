"""The drafted reply to a ticket and the policy passages it cites."""

from pydantic import BaseModel


class Citation(BaseModel):
    """A policy passage the reply cites, with the text quoted from it."""

    source: str  # document name, e.g. "refunds.md"
    ordinal: int  # part of the document
    quotes: list[str]  # cited_text from the API, in the order the reply cites it

    @property
    def citation(self) -> str:
        """Same label as ``KnowledgePassage.citation``, e.g. ``refunds.md#1``."""
        return f"{self.source}#{self.ordinal}"


class Reply(BaseModel):
    """A draft for a person to review and send; never sent automatically."""

    text: str  # with [n] after each cited part and the sources listed at the end
    citations: list[Citation]  # [1] is citations[0], in order of first use

    @property
    def has_sources(self) -> bool:
        """False: no policy passed the threshold, or the reply cites none."""
        return bool(self.citations)
