"""The knowledge base in PostgreSQL: chunks with their embeddings, per index."""

import hashlib
import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import TupleRow
from pydantic import SecretStr

from ..config import Settings
from ..models import KnowledgePassage
from .chunking import chunk_corpus
from .embedder import Embedder, fastembed_embedder

EMBEDDING_DIMENSIONS = 384  # BAAI/bge-small-en-v1.5

# One index per model and chunk setting, so experiments can sit side by side.
# corpus_hash tells whether the documents changed since the index was built.
SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_indexes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model text NOT NULL,
    chunk_size integer NOT NULL CHECK (chunk_size > 0),
    chunk_overlap integer NOT NULL
        CHECK (chunk_overlap >= 0 AND chunk_overlap < chunk_size),
    corpus_hash text NOT NULL,
    built_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model, chunk_size, chunk_overlap)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    index_id bigint NOT NULL REFERENCES knowledge_indexes (id) ON DELETE CASCADE,
    source text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    text text NOT NULL,
    embedding vector({EMBEDDING_DIMENSIONS}) NOT NULL,
    PRIMARY KEY (index_id, source, ordinal)
);

-- Full-text search. STORED: PostgreSQL 18 makes generated columns virtual by default,
-- and the GIN index needs stored values. The config is named, as an index requires.
ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS search_text tsvector
    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX IF NOT EXISTS knowledge_chunks_search_text
    ON knowledge_chunks USING gin (search_text);
"""


class KnowledgeDatabaseNotConfiguredError(RuntimeError):
    """KNOWLEDGE_DATABASE_URL is not set."""


class KnowledgeIndexMissingError(LookupError):
    """No index for this model and chunk setting: run ``make kb-index``."""


class EmbeddingDimensionsError(ValueError):
    """The embedder's vectors do not fit the ``embedding`` column."""


@dataclass(frozen=True)
class BuildResult:
    index_id: int
    chunk_count: int
    reused: bool  # True: documents unchanged, nothing was embedded


def fetch_one(cursor: psycopg.Cursor[TupleRow]) -> TupleRow:
    """The row of a query that always returns one: ``RETURNING``, ``count(*)``."""
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("the query returned no row")
    return row


def create_schema(connection: psycopg.Connection) -> None:
    """Create the extension and tables if missing. Safe to run every time."""
    connection.execute(SCHEMA)  # several statements: allowed without parameters
    register_vector(connection)  # needs the extension, so only after it exists


@contextmanager
def open_knowledge_db(url: SecretStr | None) -> Generator[psycopg.Connection]:
    """Connect, make sure the schema exists, commit on success, close after use."""
    if url is None:
        raise KnowledgeDatabaseNotConfiguredError(
            "Set KNOWLEDGE_DATABASE_URL in .env, see .env.example"
        )
    with psycopg.connect(url.get_secret_value()) as connection:
        create_schema(connection)
        yield connection


@contextmanager
def open_knowledge_base(
    settings: Settings, download: bool = False
) -> Generator[KnowledgeBase]:
    """The knowledge base from the settings: local model, PostgreSQL connection."""

    embedder = fastembed_embedder(download)

    with open_knowledge_db(settings.knowledge_database_url) as connection:
        yield KnowledgeBase(
            connection, embedder, settings.chunk_size, settings.chunk_overlap
        )


def corpus_hash(docs: dict[str, str]) -> str:
    """Fingerprint of all documents; independent of their order in ``docs``."""
    canonical = json.dumps(sorted(docs.items()), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class KnowledgeBase:
    """Chunks of one index: one embedding model and one chunk setting."""

    connection: psycopg.Connection
    embedder: Embedder
    chunk_size: int
    chunk_overlap: int

    def build(self, docs: dict[str, str]) -> BuildResult:
        """Index ``docs`` ({source: text}), unless they are unchanged since last time.

        Embedding happens before the write, so a failure leaves the old index as is.
        """
        if self.embedder.dimensions != EMBEDDING_DIMENSIONS:
            raise EmbeddingDimensionsError(
                f"{self.embedder.model} makes {self.embedder.dimensions} dimensions, "
                f"the database stores {EMBEDDING_DIMENSIONS}"
            )
        fingerprint = corpus_hash(docs)
        existing = self.find_index()
        if existing is not None and existing[1] == fingerprint:
            return BuildResult(existing[0], self.count_chunks(existing[0]), reused=True)

        chunks = chunk_corpus(docs, self.chunk_size, self.chunk_overlap)
        vectors = self.embedder.embed_passages([chunk.text for chunk in chunks])

        with self.connection.transaction():
            (index_id,) = fetch_one(
                self.connection.execute(
                    "INSERT INTO knowledge_indexes"
                    " (model, chunk_size, chunk_overlap, corpus_hash)"
                    " VALUES (%s, %s, %s, %s)"
                    " ON CONFLICT (model, chunk_size, chunk_overlap) DO UPDATE"
                    " SET corpus_hash = EXCLUDED.corpus_hash, built_at = now()"
                    " RETURNING id",
                    (
                        self.embedder.model,
                        self.chunk_size,
                        self.chunk_overlap,
                        fingerprint,
                    ),
                )
            )
            # The old chunks of this index only; other indexes stay as they are.
            self.connection.execute(
                "DELETE FROM knowledge_chunks WHERE index_id = %s", (index_id,)
            )
            with self.connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO knowledge_chunks"
                    " (index_id, source, ordinal, text, embedding)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    [
                        (index_id, chunk.source, chunk.ordinal, chunk.text, vector)
                        for chunk, vector in zip(chunks, vectors, strict=True)
                    ],
                )
        return BuildResult(index_id, len(chunks), reused=False)

    def search(self, query: str, k: int) -> list[KnowledgePassage]:
        """The ``k`` chunks closest in meaning to ``query``, best first.

        Exact search over all chunks of this index; fast enough for a few thousand.
        """
        if k <= 0:
            raise ValueError("k must be positive")
        index_id = self.require_index()
        vector = self.embedder.embed_query(query)
        if not np.any(vector):  # no direction: cosine is undefined (NaN)
            return []
        rows = self.connection.execute(
            "SELECT source, ordinal, text, 1 - (embedding <=> %(query)s) AS score"
            " FROM knowledge_chunks WHERE index_id = %(index_id)s"
            " ORDER BY embedding <=> %(query)s LIMIT %(k)s",
            {"query": vector, "index_id": index_id, "k": k},
        ).fetchall()
        return [
            KnowledgePassage(source=source, ordinal=ordinal, text=text, score=score)
            for source, ordinal, text, score in rows
        ]

    def keyword_search(self, query: str, k: int) -> list[KnowledgePassage]:
        """The ``k`` chunks that share the most words with ``query``, best first.

        PostgreSQL full-text search, for comparison with ``search`` in kb-eval; the
        workflow does not use it. Words are stemmed and stop words dropped. Any word
        matches (OR): with AND, as in ``websearch_to_tsquery``, a ticket long enough
        to describe its problem matches no chunk. The score is ``ts_rank_cd``, not
        comparable with the cosine similarity of ``search``.
        """
        if k <= 0:
            raise ValueError("k must be positive")
        index_id = self.require_index()
        # The ticket's own lexemes, joined with |. 'simple' keeps them as they are:
        # they are stemmed already. Only stop words: NULL, which matches nothing.
        rows = self.connection.execute(
            "WITH words AS ("
            "  SELECT to_tsquery('simple', string_agg(quote_literal(lexeme), ' | '))"
            "  AS query FROM unnest(to_tsvector('english', %(query)s))"
            ")"
            " SELECT source, ordinal, text, ts_rank_cd(search_text, words.query)"
            " AS score FROM knowledge_chunks, words"
            " WHERE index_id = %(index_id)s AND search_text @@ words.query"
            " ORDER BY score DESC, source, ordinal LIMIT %(k)s",
            {"query": query, "index_id": index_id, "k": k},
        ).fetchall()
        return [
            KnowledgePassage(source=source, ordinal=ordinal, text=text, score=score)
            for source, ordinal, text, score in rows
        ]

    def require_index(self) -> int:
        """Id of this index; ``KnowledgeIndexMissingError`` if it was not built."""
        index = self.find_index()
        if index is None:
            raise KnowledgeIndexMissingError(self.missing_index_message())
        return index[0]

    def find_index(self) -> tuple[int, str] | None:
        """Id and corpus hash of this index, if it was built."""
        return self.connection.execute(
            "SELECT id, corpus_hash FROM knowledge_indexes"
            " WHERE model = %s AND chunk_size = %s AND chunk_overlap = %s",
            (self.embedder.model, self.chunk_size, self.chunk_overlap),
        ).fetchone()

    def missing_index_message(self) -> str:
        built = self.connection.execute(
            "SELECT model, chunk_size, chunk_overlap FROM knowledge_indexes"
            " ORDER BY model, chunk_size, chunk_overlap"
        ).fetchall()
        existing = ", ".join(
            f"{model} {size}/{overlap}" for model, size, overlap in built
        )
        return (
            f"No knowledge index for {self.embedder.model} with chunk size "
            f"{self.chunk_size} and overlap {self.chunk_overlap}. Run: make kb-index. "
            f"Built (model size/overlap): {existing or 'none'}"
        )

    def count_chunks(self, index_id: int) -> int:
        row = fetch_one(
            self.connection.execute(
                "SELECT count(*) FROM knowledge_chunks WHERE index_id = %s", (index_id,)
            )
        )
        count: int = row[0]
        return count
