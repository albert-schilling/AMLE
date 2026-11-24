"""What every workflow run gets besides its state: LangGraph's runtime context.

Not saved in checkpoints, so it can hold a database connection.
"""

from dataclasses import dataclass
from typing import Protocol

from .models import KnowledgePassage


class KnowledgeSearch(Protocol):
    """What the workflow needs from the knowledge base; tests use a fake."""

    def require_index(self) -> int: ...

    def search(self, query: str, k: int) -> list[KnowledgePassage]: ...


@dataclass(frozen=True)
class WorkflowContext:
    knowledge: KnowledgeSearch
