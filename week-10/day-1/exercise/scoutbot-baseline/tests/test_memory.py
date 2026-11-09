"""Offline tests for the per-customer memory store.

Same design rule as `test_knowledge.py`, because `MemoryStore` is `KnowledgeBase` pointed at a
different question: the thing that needs the network - the embedder - is injected, so every test here
hands it a tiny hand-written embedder and checks the *scope and ranking logic* with no model, no
download and no network. What these tests are really about is the two differences memory adds over
retrieval: recall is scoped to one `customer_id`, and write is idempotent on `ticket_id`. One opt-in
test at the bottom exercises the real fastembed path and is skipped unless `SCOUTBOT_EMBED_TEST=1`.
"""
import os

import numpy as np
import pytest

from scoutbot.memory import MEMORY_RELEVANCE, MemoryStore, Recalled, format_memories

# A fake embedder over four named axes, same trick as the knowledge tests: a text points along the
# axes whose keyword it contains, so "my refund never came" and "where is my refund" both land on the
# refund axis and score near 1.0 against each other - the semantic-neighbours property real embeddings
# have, reproduced deterministically so recall is testable without a model.
_AXES = ["refund", "shipping", "warranty", "billing"]
_AXIS_WORDS = {
    "refund": ("refund", "refunds", "money", "returned"),
    "shipping": ("shipping", "delivery", "deliver", "ship", "parcel"),
    "warranty": ("warranty", "broken", "defect", "defective"),
    "billing": ("billing", "charged", "charge", "invoice", "twice"),
}


def keyword_embedder(texts):
    vecs = []
    for text in texts:
        low = text.lower()
        vec = np.array(
            [1.0 if any(w in low for w in _AXIS_WORDS[axis]) else 0.0 for axis in _AXES],
            dtype=np.float32,
        )
        if not vec.any():
            vec = np.ones(len(_AXES), dtype=np.float32)  # equally unlike everything -> ties
        vecs.append(vec)
    return vecs


# ---------- writing, and the idempotency guard ----------
def test_write_stores_a_memory_and_counts_it():
    store = MemoryStore(keyword_embedder)
    assert store.write("1001", "T-1", "asked about a late refund") is True
    assert store.count() == 1
    assert store.count("1001") == 1


def test_write_is_idempotent_on_ticket_id():
    """The send-ledger's discipline, applied to remembering: writing the same ticket twice stores it
    once, so a resumed or re-run ticket never grows a duplicate memory."""
    store = MemoryStore(keyword_embedder)
    assert store.write("1001", "T-1", "asked about a late refund") is True
    assert store.write("1001", "T-1", "asked about a late refund") is False
    assert store.count("1001") == 1


def test_the_same_ticket_id_for_a_different_customer_is_a_separate_memory():
    """The key is the pair, not the ticket alone: two customers can each have a 'T-1' and neither
    dedupes the other away."""
    store = MemoryStore(keyword_embedder)
    assert store.write("1001", "T-1", "a refund question") is True
    assert store.write("2002", "T-1", "a shipping question") is True
    assert store.count() == 2
    assert store.count("1001") == 1
    assert store.count("2002") == 1


# ---------- recall: scoped, ranked, thresholded ----------
def _seeded_store():
    store = MemoryStore(keyword_embedder)
    store.write("1001", "T-1", "my refund never arrived")
    store.write("1001", "T-2", "a duplicate charge on my invoice")
    store.write("2002", "T-9", "where is my delivery")
    return store


def test_recall_returns_only_this_customers_memories():
    """The privacy property is a where-clause: one customer's history is structurally invisible to
    another's, so a shipping question from 2002 never surfaces 1001's refund line."""
    store = _seeded_store()
    hits = store.recall("1001", "where is my delivery parcel")
    assert all(h.ticket_id in {"T-1", "T-2"} for h in hits)
    assert "T-9" not in {h.ticket_id for h in hits}


def test_recall_ranks_the_relevant_memory_first():
    store = _seeded_store()
    hits = store.recall("1001", "I want my money returned")
    assert hits[0].ticket_id == "T-1"
    assert isinstance(hits[0], Recalled)
    assert 0.0 <= hits[0].score <= 1.0001


def test_recall_drops_memories_below_the_relevance_floor():
    """Unlike retrieval, which must return its best guess for the critique to judge, recall would
    rather surface nothing than pad a draft with an unrelated past ticket."""
    store = MemoryStore(keyword_embedder)
    store.write("1001", "T-1", "a warranty claim for a broken part")
    # A billing query is orthogonal to the warranty memory, so it scores 0.0 and is filtered out.
    assert store.recall("1001", "I was charged twice") == []


def test_recall_respects_k():
    store = MemoryStore(keyword_embedder)
    for i in range(5):
        store.write("1001", f"T-{i}", "a refund question about money returned")
    assert len(store.recall("1001", "refund", k=2)) == 2


def test_recall_of_an_unknown_customer_is_empty_not_an_error():
    """The normal first-contact case: nothing on file recalls an empty list, which the graph treats
    as 'no memory', not a failure."""
    store = _seeded_store()
    assert store.recall("9999", "anything at all") == []


def test_recall_min_score_can_be_overridden():
    """The floor is a default, not a law: a caller that wants everything this customer has can drop
    it to zero."""
    store = MemoryStore(keyword_embedder)
    store.write("1001", "T-1", "a warranty claim for a broken part")
    assert store.recall("1001", "I was charged twice", min_score=0.0) != []


def test_the_relevance_floor_is_lower_than_the_retrieval_floor():
    """A deliberate judgement worth pinning down: a weak *recall* only adds reviewed background, so
    memory errs toward remembering, where a weak *retrieval* grounds a factual reply and errs toward
    silence with a higher floor."""
    from scoutbot.knowledge import LOW_CONFIDENCE

    assert MEMORY_RELEVANCE < LOW_CONFIDENCE


# ---------- formatting recalled memory for a draft prompt ----------
def test_format_memories_tags_each_ticket_and_does_not_cite():
    """The shape is deliberately unlike `format_passages`: a `(ticket ...)` tag for tracing, and no
    `[source]`, because memory is background the model may use but must never cite."""
    memories = [
        Recalled("T-1", "asked about a late refund", 0.7),
        Recalled("T-2", "a duplicate charge", 0.6),
    ]
    block = format_memories(memories)
    assert block == "- (ticket T-1) asked about a late refund\n- (ticket T-2) a duplicate charge"
    assert "[" not in block  # no citation brackets anywhere


def test_format_memories_accepts_plain_state_dicts():
    """The graph keeps recalled memories as dicts so they survive the checkpointer; the formatter has
    to render those identically to the `Recalled` objects `recall` returns."""
    as_dicts = [{"ticket_id": "T-1", "text": "asked about a late refund", "score": 0.7}]
    assert format_memories(as_dicts) == "- (ticket T-1) asked about a late refund"


def test_format_memories_empty_is_empty_string():
    assert format_memories([]) == ""


# ---------- persistence ----------
def test_memory_survives_into_a_second_store_on_the_same_file(tmp_path):
    """The durability story is the checkpointer's and the ledger's, pointed at memory: what a customer
    was remembered for last week is still there this week, across a fresh connection."""
    path = tmp_path / "memory.db"
    store = MemoryStore(keyword_embedder, db_path=path)
    store.write("1001", "T-1", "my refund never arrived")
    store.close()

    reopened = MemoryStore(keyword_embedder, db_path=path)
    assert reopened.count("1001") == 1
    assert reopened.recall("1001", "where is my refund money")[0].ticket_id == "T-1"


# ---------- the one real-model test, opt-in ----------
@pytest.mark.skipif(
    os.environ.get("SCOUTBOT_EMBED_TEST") != "1",
    reason="set SCOUTBOT_EMBED_TEST=1 to run the real fastembed download/embed test",
)
def test_real_fastembed_recalls_the_semantically_closest_ticket():
    from scoutbot.knowledge import fastembed_embedder

    store = MemoryStore(fastembed_embedder())
    store.write("1001", "T-1", "My refund still has not been paid back to my card.")
    store.write("1001", "T-2", "The parcel was left at the wrong address.")
    top = store.recall("1001", "when will my money come back", k=1)[0]
    assert top.ticket_id == "T-1"
