"""Offline tests for the knowledge base.

The design rule here is the same one the rest of this repo uses for the model: the thing that needs
the network is injected, so it can be faked. `KnowledgeBase` takes an `embed` function, so every test
below hands it a tiny hand-written embedder and checks the *ranking logic* with no model, no download
and no network. Exactly one test at the bottom exercises the real fastembed path, and it is skipped
unless `SCOUTBOT_EMBED_TEST=1`, so the suite stays fast and offline by default.
"""
import os

import numpy as np
import pytest

from scoutbot.knowledge import (
    Chunk,
    KnowledgeBase,
    chunk_corpus,
    chunk_document,
    cosine_scores,
    load_corpus,
)

# A fake embedder over four named axes. Each text is placed on the axes whose keyword it contains, so
# "refunds take five days" and "how long do refunds take" both point mostly along the refund axis and
# rank near each other - the property real embeddings have, reproduced deterministically in one line.
_AXES = ["refund", "shipping", "warranty", "billing"]


def keyword_embedder(texts):
    vecs = []
    for text in texts:
        low = text.lower()
        vec = np.array([1.0 if axis in low else 0.0 for axis in _AXES], dtype=np.float32)
        if not vec.any():
            vec = np.ones(len(_AXES), dtype=np.float32)  # equally unlike everything
        vecs.append(vec)
    return vecs


# ---------- chunking ----------
def test_chunk_document_windows_and_overlap():
    text = " ".join(str(i) for i in range(100))  # 100 one-word "sentences"
    chunks = chunk_document(text, size=40, overlap=10)
    # step = 30, so windows start at 0, 30, 60; the window at 60 (words 60-99) already reaches the
    # end, so the loop stops there rather than emitting a redundant tail window -> 3 chunks.
    assert len(chunks) == 3
    assert chunks[0].split()[:3] == ["0", "1", "2"]
    assert chunks[-1].split()[-1] == "99"
    # Overlap: the last 10 words of chunk 0 reappear as the first 10 of chunk 1.
    assert chunks[0].split()[-10:] == chunks[1].split()[:10]


def test_chunk_document_keeps_short_tail():
    text = " ".join(str(i) for i in range(45))
    chunks = chunk_document(text, size=40, overlap=10)
    # Windows at 0 and 30; the second is only 15 words and must be kept, not dropped.
    assert len(chunks) == 2
    assert len(chunks[1].split()) == 15


def test_chunk_document_single_chunk_when_short():
    assert chunk_document("just a few words", size=60, overlap=10) == ["just a few words"]


def test_chunk_document_empty_is_no_chunks():
    assert chunk_document("   ", size=60, overlap=10) == []


def test_chunk_document_rejects_overlap_not_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_document("a b c", size=10, overlap=10)


def test_chunk_corpus_tags_source_and_ordinal():
    docs = {"refunds": " ".join(["w"] * 90), "shipping": "short doc"}
    chunks = chunk_corpus(docs, size=60, overlap=10)
    refund_chunks = [c for c in chunks if c.source == "refunds"]
    assert [c.ordinal for c in refund_chunks] == [0, 1]
    assert any(c.source == "shipping" and c.ordinal == 0 for c in chunks)


def test_load_corpus_reads_md_stems(tmp_path):
    (tmp_path / "refunds.md").write_text("refund text", encoding="utf-8")
    (tmp_path / "shipping.md").write_text("shipping text", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("not markdown", encoding="utf-8")
    docs = load_corpus(tmp_path)
    assert set(docs) == {"refunds", "shipping"}
    assert docs["refunds"] == "refund text"


# ---------- cosine ----------
def test_cosine_scores_ranks_by_direction():
    matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]], dtype=np.float32)
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    scores = cosine_scores(matrix, query)
    order = list(np.argsort(-scores))
    assert order[0] == 0  # exact direction match wins
    assert order[1] == 2  # mostly-aligned next
    assert order[2] == 1  # orthogonal last


def test_cosine_scores_handles_zero_vector_without_nan():
    matrix = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32)
    scores = cosine_scores(matrix, np.array([1.0, 0.0, 0.0], dtype=np.float32))
    assert not np.isnan(scores).any()


def test_cosine_scores_empty_matrix():
    scores = cosine_scores(np.empty((0, 3), dtype=np.float32), np.array([1.0, 0.0, 0.0]))
    assert scores.shape == (0,)


# ---------- store + search ----------
def _kb():
    kb = KnowledgeBase(keyword_embedder)
    kb.index(
        [
            Chunk("refunds", 0, "refunds are issued within five business days"),
            Chunk("shipping", 0, "shipping is free over fifty euros"),
            Chunk("warranty", 0, "the warranty covers manufacturing defects"),
            Chunk("billing", 0, "billing renews automatically each month"),
        ]
    )
    return kb


def test_search_returns_topk_most_similar_first():
    kb = _kb()
    hits = kb.search("how long do refunds take", k=2)
    assert hits[0].source == "refunds"
    assert len(hits) == 2
    assert hits[0].score >= hits[1].score


def test_search_reports_source_and_score():
    kb = _kb()
    top = kb.search("a warranty question", k=1)[0]
    assert top.source == "warranty"
    assert 0.0 <= top.score <= 1.0001


def test_search_empty_store_returns_empty():
    kb = KnowledgeBase(keyword_embedder)
    assert kb.search("anything", k=3) == []


def test_index_appends_and_counts():
    kb = KnowledgeBase(keyword_embedder)
    assert kb.index([Chunk("refunds", 0, "refund one")]) == 1
    assert kb.index([Chunk("refunds", 1, "refund two")]) == 1
    assert kb.count() == 2


def test_index_empty_is_noop():
    kb = KnowledgeBase(keyword_embedder)
    assert kb.index([]) == 0
    assert kb.count() == 0


def test_build_from_dict_indexes_all_chunks():
    docs = {"refunds": " ".join(["refund"] * 90), "shipping": "shipping is free"}
    kb = KnowledgeBase.build(docs, keyword_embedder, size=60, overlap=10)
    assert kb.count() == 3  # 2 refund chunks + 1 shipping chunk


def test_search_persists_to_a_file(tmp_path):
    path = tmp_path / "kb.db"
    kb = KnowledgeBase.build(
        {"refunds": "refunds are issued within five business days"},
        keyword_embedder,
        db_path=path,
    )
    kb.close()
    # A fresh store opened on the same file can search without re-indexing.
    reopened = KnowledgeBase(keyword_embedder, db_path=path)
    assert reopened.count() == 1
    assert reopened.search("refund", k=1)[0].source == "refunds"


# ---------- the one real-model test, opt-in ----------
@pytest.mark.skipif(
    os.environ.get("SCOUTBOT_EMBED_TEST") != "1",
    reason="set SCOUTBOT_EMBED_TEST=1 to run the real fastembed download/embed test",
)
def test_real_fastembed_ranks_refund_query_to_refund_doc():
    from scoutbot.knowledge import fastembed_embedder

    kb = KnowledgeBase.build(
        {
            "refunds": "Refunds are issued to the original payment method within five business days.",
            "shipping": "Standard shipping is free on orders over fifty euros.",
            "warranty": "The two-year warranty covers manufacturing defects.",
        },
        fastembed_embedder(),
    )
    top = kb.search("how long until my money is returned", k=1)[0]
    assert top.source == "refunds"
