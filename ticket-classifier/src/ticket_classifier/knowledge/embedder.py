"""Turn text into vectors. Only ``fastembed_embedder`` knows about fastembed.

The rest of the knowledge base depends on the ``Embedder`` protocol, so tests use a
small fake and never load a model.
"""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..config import get_settings

if TYPE_CHECKING:  # for type checkers only: fastembed loads onnxruntime, slow
    from fastembed import TextEmbedding

Vector = NDArray[np.float32]


class Embedder(Protocol):
    model: str  # vectors of different models cannot be compared
    dimensions: int

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        """Vectors for stored text, one per text, in the same order."""
        ...

    def embed_query(self, text: str) -> Vector:
        """The vector for a search query."""
        ...


class EmbeddingModelMissingError(RuntimeError):
    """The model is not in the local cache, and downloading was not allowed."""


@dataclass(frozen=True)
class FastEmbedEmbedder:
    model: str
    dimensions: int
    engine: TextEmbedding

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return [as_vector(v) for v in self.engine.passage_embed(list(texts))]

    def embed_query(self, text: str) -> Vector:
        (vector,) = self.engine.query_embed([text])
        return as_vector(vector)


def as_vector(values: ArrayLike) -> Vector:
    return np.asarray(values, dtype=np.float32)


def fastembed_embedder(download: bool = False) -> FastEmbedEmbedder:
    """The local embedding model from the settings.

    With ``download=False`` it never goes online, so only indexing may download.
    """
    settings = get_settings()
    # Read when huggingface_hub is imported, so it must be set before fastembed.
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from fastembed import TextEmbedding  # slow to import: loads onnxruntime

    try:
        engine = TextEmbedding(
            settings.embedding_model,
            cache_dir=str(settings.embedding_cache_path),
            local_files_only=not download,
        )
    except ValueError:  # fastembed's only signal for "not in the cache"
        if download:
            raise
        raise EmbeddingModelMissingError(
            f"Embedding model {settings.embedding_model} is not downloaded yet. "
            "Run: make kb-index"
        ) from None
    return FastEmbedEmbedder(settings.embedding_model, engine.embedding_size, engine)
