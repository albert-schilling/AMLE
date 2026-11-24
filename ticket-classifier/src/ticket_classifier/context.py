"""What every workflow run gets besides its state: LangGraph's runtime context.

Not saved in checkpoints, so it can hold a database connection.
"""

from dataclasses import dataclass

from .knowledge.store import KnowledgeSearch


@dataclass(frozen=True)
class WorkflowContext:
    knowledge: KnowledgeSearch
