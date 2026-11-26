"""What every workflow run gets besides its state: LangGraph's runtime context.

Not saved in checkpoints, so it can hold a database connection.
"""

from dataclasses import dataclass
from typing import Protocol

from langgraph.runtime import Runtime

from .models import KnowledgePassage, Search, Ticket


class KnowledgeSearch(Protocol):
    """What the workflow needs from the knowledge base; tests use a fake."""

    def require_index(self) -> int: ...

    def search(self, query: str, k: int) -> list[KnowledgePassage]: ...


class QueryWriter(Protocol):
    """Writes the next search query for a ticket; after failed searches, a new one.

    ``queries.write_query`` asks the model; tests use a fake.
    """

    def __call__(self, ticket: Ticket, search: Search) -> str: ...


@dataclass(frozen=True)
class WorkflowContext:
    knowledge: KnowledgeSearch
    write_query: QueryWriter


class MissingContextError(RuntimeError):
    """The run was started without a ``WorkflowContext``."""


def require_context(runtime: Runtime[WorkflowContext], node: str) -> WorkflowContext:
    """The run's context; raises ``MissingContextError`` if it was started without."""
    if runtime.context is None:
        raise MissingContextError(f"{node} needs a WorkflowContext")
    return runtime.context
