"""Knowledge base: policy documents cut into chunks, embedded and searched.

The rest of the app imports from here. Submodules hold the details; only tests
import those directly.
"""

from .documents import NoDocumentsError, load_documents
from .embedder import EmbeddingModelMissingError
from .evaluation import (
    ChunkSettingResult,
    KnowledgeEvaluation,
    SearchQuality,
    ThresholdResult,
    compare_chunk_settings,
    compare_thresholds,
    load_questions,
    results_table,
    thresholds_table,
)
from .store import (
    BuildResult,
    KnowledgeDatabaseNotConfiguredError,
    KnowledgeIndexMissingError,
    open_knowledge_base,
)

__all__ = [
    "BuildResult",
    "ChunkSettingResult",
    "EmbeddingModelMissingError",
    "KnowledgeDatabaseNotConfiguredError",
    "KnowledgeEvaluation",
    "KnowledgeIndexMissingError",
    "NoDocumentsError",
    "SearchQuality",
    "ThresholdResult",
    "compare_chunk_settings",
    "compare_thresholds",
    "load_documents",
    "load_questions",
    "open_knowledge_base",
    "results_table",
    "thresholds_table",
]
