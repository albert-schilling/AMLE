import numpy as np
import pytest
from helpers import KeywordEmbedder
from psycopg import errors

from ticket_classifier import commands
from ticket_classifier.config import get_settings
from ticket_classifier.knowledge.store import (
    EMBEDDING_DIMENSIONS,
    BuildResult,
    EmbeddingDimensionsError,
    KnowledgeBase,
    KnowledgeDatabaseNotConfiguredError,
    KnowledgeIndexMissingError,
    corpus_hash,
    create_schema,
    open_knowledge_db,
)

postgres = pytest.mark.postgres


def add_index(connection, chunk_size=60, chunk_overlap=10):
    return connection.execute(
        "INSERT INTO knowledge_indexes (model, chunk_size, chunk_overlap, corpus_hash)"
        " VALUES ('m', %s, %s, 'h') RETURNING id",
        (chunk_size, chunk_overlap),
    ).fetchone()[0]


def add_chunk(connection, index_id, vector):
    connection.execute(
        "INSERT INTO knowledge_chunks VALUES (%s, 'a.md', 0, 'text', %s)",
        (index_id, vector),
    )


def test_missing_database_url_names_the_fix():
    with pytest.raises(KnowledgeDatabaseNotConfiguredError, match="KNOWLEDGE_DATA"):
        with open_knowledge_db(None):
            pass


@postgres
def test_schema_can_be_created_twice(knowledge_db):
    create_schema(knowledge_db)
    create_schema(knowledge_db)

    tables = knowledge_db.execute(
        "SELECT tablename FROM pg_tables WHERE tablename LIKE 'knowledge_%'"
        " ORDER BY tablename"
    ).fetchall()
    assert tables == [("knowledge_chunks",), ("knowledge_indexes",)]


@postgres
def test_vectors_round_trip_as_float32(knowledge_db):
    create_schema(knowledge_db)
    vector = np.linspace(-1, 1, EMBEDDING_DIMENSIONS, dtype=np.float32)

    add_chunk(knowledge_db, add_index(knowledge_db), vector)

    (stored,) = knowledge_db.execute(
        "SELECT embedding FROM knowledge_chunks"
    ).fetchone()
    np.testing.assert_array_equal(stored.to_numpy(), vector)


@postgres
def test_vector_of_wrong_length_is_rejected(knowledge_db):
    create_schema(knowledge_db)

    with pytest.raises(errors.DataException, match="expected 384 dimensions"):
        add_chunk(knowledge_db, add_index(knowledge_db), np.ones(3, dtype=np.float32))


@postgres
def test_overlap_not_below_chunk_size_is_rejected(knowledge_db):
    create_schema(knowledge_db)

    with pytest.raises(errors.CheckViolation):
        add_index(knowledge_db, chunk_size=10, chunk_overlap=10)


DOCS = {
    "refunds.md": "refund within thirty days refund to the card",
    "shipping.md": "shipping takes three days",
}


def knowledge_base(connection, embedder=None, chunk_size=4, chunk_overlap=1):
    create_schema(connection)
    return KnowledgeBase(
        connection, embedder or KeywordEmbedder(), chunk_size, chunk_overlap
    )


def stored_chunks(connection, index_id):
    return connection.execute(
        "SELECT source, ordinal, text FROM knowledge_chunks WHERE index_id = %s"
        " ORDER BY source, ordinal",
        (index_id,),
    ).fetchall()


def test_corpus_hash_ignores_document_order():
    reordered = dict(reversed(DOCS.items()))

    assert corpus_hash(reordered) == corpus_hash(DOCS)
    assert corpus_hash({**DOCS, "shipping.md": "changed"}) != corpus_hash(DOCS)


@postgres
def test_build_indexes_every_chunk(knowledge_db):
    result = knowledge_base(knowledge_db).build(DOCS)

    assert result.reused is False
    assert result.chunk_count == 4
    assert stored_chunks(knowledge_db, result.index_id) == [
        ("refunds.md", 0, "refund within thirty days"),
        ("refunds.md", 1, "days refund to the"),
        ("refunds.md", 2, "the card"),
        ("shipping.md", 0, "shipping takes three days"),
    ]


@postgres
def test_unchanged_documents_are_not_embedded_again(knowledge_db):
    embedder = KeywordEmbedder()
    first = knowledge_base(knowledge_db, embedder).build(DOCS)
    embedded = embedder.embedded_texts

    second = knowledge_base(knowledge_db, embedder).build(DOCS)

    assert second == BuildResult(first.index_id, 4, reused=True)
    assert embedder.embedded_texts == embedded


@postgres
def test_changed_documents_replace_the_old_chunks(knowledge_db):
    first = knowledge_base(knowledge_db).build(DOCS)

    second = knowledge_base(knowledge_db).build({"warranty.md": "warranty two years"})

    assert second.index_id == first.index_id
    assert second.reused is False
    assert stored_chunks(knowledge_db, second.index_id) == [
        ("warranty.md", 0, "warranty two years")
    ]


@postgres
def test_another_chunk_setting_is_a_separate_index(knowledge_db):
    small = knowledge_base(knowledge_db, chunk_size=4).build(DOCS)

    large = knowledge_base(knowledge_db, chunk_size=10).build(DOCS)

    assert large.index_id != small.index_id
    assert knowledge_base(knowledge_db).count_chunks(small.index_id) == 4
    assert large.chunk_count == 2


@postgres
def test_embedder_with_other_dimensions_is_rejected_before_writing(knowledge_db):
    embedder = KeywordEmbedder()
    embedder.dimensions = 3

    with pytest.raises(EmbeddingDimensionsError, match="3 dimensions"):
        knowledge_base(knowledge_db, embedder).build(DOCS)

    (count,) = knowledge_db.execute("SELECT count(*) FROM knowledge_indexes").fetchone()
    assert count == 0


SEARCH_DOCS = {
    "refunds.md": "refund refund money back",
    "shipping.md": "shipping parcel tracking",
    "warranty.md": "warranty repair shipping",
}


@postgres
def test_search_ranks_the_matching_chunk_first(knowledge_db):
    knowledge = knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0)
    knowledge.build(SEARCH_DOCS)

    hits = knowledge.search("where is my shipping parcel", k=2)

    assert [(hit.source, hit.ordinal) for hit in hits] == [
        ("shipping.md", 0),
        ("warranty.md", 0),
    ]
    assert hits[0].text == "shipping parcel tracking"
    assert hits[0].score == pytest.approx(1)
    assert hits[0].score > hits[1].score


@postgres
def test_keyword_search_finds_stemmed_words(knowledge_db):
    knowledge = knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0)
    knowledge.build(SEARCH_DOCS)

    hits = knowledge.keyword_search("shipped", k=3)  # stem of "shipping"

    assert {hit.source for hit in hits} == {"shipping.md", "warranty.md"}
    assert all(hit.score > 0 for hit in hits)


@postgres
def test_keyword_search_needs_any_word_and_ranks_more_shared_words_first(
    knowledge_db,
):
    knowledge = knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0)
    knowledge.build(SEARCH_DOCS)

    hits = knowledge.keyword_search("repair of the shipping, it's late", k=3)

    assert [hit.source for hit in hits] == ["warranty.md", "shipping.md"]
    assert hits[0].score > hits[1].score


@postgres
def test_keyword_search_with_only_stop_words_finds_nothing(knowledge_db):
    knowledge = knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0)
    knowledge.build(SEARCH_DOCS)

    assert knowledge.keyword_search("can I do it", k=3) == []


@postgres
def test_keyword_search_without_index_names_the_fix(knowledge_db):
    with pytest.raises(KnowledgeIndexMissingError):
        knowledge_base(knowledge_db).keyword_search("refund", k=3)


@postgres
def test_search_scores_are_the_cosine_similarity(knowledge_db):
    embedder = KeywordEmbedder()
    knowledge = knowledge_base(knowledge_db, embedder, chunk_size=10, chunk_overlap=0)
    knowledge.build(SEARCH_DOCS)
    query = "refund for shipping"

    hits = knowledge.search(query, k=3)

    q = embedder.embed_query(query)
    for hit in hits:
        c = embedder.vector(hit.text)
        cosine = q @ c / (np.linalg.norm(q) * np.linalg.norm(c))
        assert hit.score == pytest.approx(cosine, abs=1e-6)


@postgres
def test_search_returns_at_most_k_passages(knowledge_db):
    knowledge = knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0)
    knowledge.build(SEARCH_DOCS)

    assert len(knowledge.search("refund shipping warranty", k=2)) == 2
    assert len(knowledge.search("refund shipping warranty", k=10)) == 3


@postgres
def test_search_of_an_empty_index_returns_nothing(knowledge_db):
    knowledge = knowledge_base(knowledge_db)
    knowledge.build({})

    assert knowledge.search("refund", k=3) == []


@postgres
def test_query_without_known_words_returns_nothing_instead_of_nan(knowledge_db):
    knowledge = knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0)
    knowledge.build(SEARCH_DOCS)

    assert knowledge.search("capital of france", k=3) == []


@postgres
def test_search_without_index_names_the_fix_and_the_built_ones(knowledge_db):
    knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0).build(SEARCH_DOCS)

    with pytest.raises(KnowledgeIndexMissingError) as error:
        knowledge_base(knowledge_db, chunk_size=60, chunk_overlap=10).search("x", k=3)

    assert "make kb-index" in str(error.value)
    assert "fake-keyword 10/0" in str(error.value)


@postgres
def test_require_index_returns_the_built_index(knowledge_db):
    knowledge = knowledge_base(knowledge_db, chunk_size=10, chunk_overlap=0)
    result = knowledge.build(SEARCH_DOCS)

    assert knowledge.require_index() == result.index_id


def test_search_rejects_k_below_one():
    knowledge = KnowledgeBase(None, KeywordEmbedder(), chunk_size=4, chunk_overlap=1)

    with pytest.raises(ValueError, match="k must be positive"):
        knowledge.search("refund", k=0)


@postgres
def test_index_knowledge_builds_from_the_settings(
    knowledge_db, mocker, monkeypatch, tmp_path
):
    (tmp_path / "refunds.md").write_text("refund refund money back")
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("CHUNK_SIZE", "10")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    mocker.patch(
        "ticket_classifier.knowledge.store.fastembed_embedder",
        return_value=KeywordEmbedder(),
    )
    open_db = mocker.patch("ticket_classifier.knowledge.store.open_knowledge_db")
    open_db.return_value.__enter__.return_value = knowledge_db
    create_schema(knowledge_db)

    first = commands.index_knowledge(get_settings())
    second = commands.index_knowledge(get_settings())

    assert (first.chunk_count, first.reused) == (1, False)
    assert second.reused is True
