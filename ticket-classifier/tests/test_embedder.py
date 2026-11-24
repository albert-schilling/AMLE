"""The one test with the real model. Skipped unless RUN_EMBEDDING_TEST=1.

The first run downloads the model (about 67 MB) to output/fastembed.
"""

import os
from pathlib import Path

import numpy as np
import pytest

from ticket_classifier.knowledge.embedder import (
    EmbeddingModelMissingError,
    fastembed_embedder,
)

MODEL_CACHE = Path(__file__).parents[1] / "output" / "fastembed"


def test_missing_model_without_download_names_the_fix(monkeypatch, tmp_path):
    monkeypatch.setenv("EMBEDDING_CACHE_PATH", str(tmp_path / "empty"))

    with pytest.raises(EmbeddingModelMissingError, match="make kb-index"):
        fastembed_embedder()


@pytest.mark.skipif(
    os.environ.get("RUN_EMBEDDING_TEST") != "1", reason="set RUN_EMBEDDING_TEST=1"
)
def test_similar_meaning_scores_higher_than_shared_topic(monkeypatch):
    monkeypatch.setenv("EMBEDDING_CACHE_PATH", str(MODEL_CACHE))
    embedder = fastembed_embedder(download=True)

    question = embedder.embed_query("how long do refunds take?")
    answer, unrelated = embedder.embed_passages(
        [
            "refunds are issued within five business days",
            "the warranty covers manufacturing defects",
        ]
    )

    assert question.shape == answer.shape == (embedder.dimensions,) == (384,)
    assert question.dtype == np.float32
    assert np.linalg.norm(question) == pytest.approx(1, abs=1e-5)
    assert question @ answer > question @ unrelated + 0.1
