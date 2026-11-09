"""ScoutBot's knowledge base: chunk a corpus, embed it, store the vectors, retrieve by meaning.

This is Week 9 Day 1, and it is the whole of retrieval with nothing agentic on top yet. There is no
model call in this file that costs money and no LangGraph node: a query goes in as a string, and the
passages most likely to answer it come back ranked. Tomorrow that ranked context is what grounds
`draft_reply`; today the job is only to make retrieval work, and to make it obvious *why* it works.

Three moving parts, in the order a query meets them:

- **Chunking** (`chunk_document`, `chunk_corpus`). A document is too big to be a unit of retrieval:
  half of a long refund page is irrelevant to "how long do refunds take". So each document is cut into
  overlapping word windows small enough to be about one thing. Overlap keeps a sentence that straddles
  a boundary from being lost to both chunks.
- **Embedding** (`EmbedFn`, `fastembed_embedder`). An embedding turns a piece of text into a vector of
  floats positioned so that texts *about the same thing* sit close together, even when they share no
  words. "how long do refunds take" and "refunds are issued within five business days" have almost no
  words in common and point in nearly the same direction. That is the one idea the whole day rests on.
- **The store and the search** (`KnowledgeBase`). The chunk vectors live as `float32` BLOBs in an
  ordinary SQLite table - the same file the checkpointer and the ledger already use in this repo, so a
  run's *knowledge* sits next to its *state*. Search embeds the query, then ranks every stored vector
  by cosine similarity in numpy. No vector database and no SQLite extension: at this corpus size a
  brute-force dot product is instant, and it keeps "retrieval is a dot product" visible rather than
  hidden behind an index.

**Why the embedder is injected rather than imported.** `KnowledgeBase` takes an `embed` function; it
never reaches for a model itself. In real use that function is `fastembed_embedder()`, which loads a
small ONNX model (no PyTorch) and needs the network exactly once, to download the model, and never
again. In a test it is a hand-written function returning fixed vectors, so the ranking logic can be
checked with no model, no download and no network - the same discipline the rest of this repo uses to
keep nodes callable without an API key.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Union

import numpy as np

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
"""The embedding model, chosen for what it does *not* drag in.

`fastembed` runs this through ONNX Runtime, so installing it pulls no PyTorch and no TensorFlow -
the single biggest cross-platform install headache avoided. The model is ~130MB, produces 384-dim
vectors, and is fetched once on first use and cached; retrieval after that is fully offline.
"""

DEFAULT_CHUNK_SIZE = 60
DEFAULT_CHUNK_OVERLAP = 10

EmbedFn = Callable[[Sequence[str]], "list[np.ndarray]"]
"""Anything that turns a list of strings into a list of `float32` vectors of equal length.

Deliberately a plain function type, not a class or a framework interface. `fastembed_embedder()`
returns one; a test writes its own in three lines. `KnowledgeBase` depends only on this shape, which
is what keeps the store testable without a real model.
"""


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit of the corpus: a slice of a document, plus where it came from.

    `source` is the document it was cut from (a filename stem like ``"refunds"``), and `ordinal` is
    its position within that document, starting at 0. Together they let a retrieved passage be cited
    back to its origin, which is exactly what Day 2 needs when a generated reply has to say which
    policy it leaned on.
    """

    source: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class Retrieved:
    """A chunk that matched a query, and how strongly it matched.

    `score` is cosine similarity in the range roughly 0..1 for this model: higher is closer in
    meaning. It is worth surfacing rather than hiding, because a top result with a low score is the
    signal that the corpus simply does not contain the answer - which is the hook the agentic days
    build on when they teach a bot to notice weak retrieval and re-query.
    """

    source: str
    ordinal: int
    text: str
    score: float


def chunk_document(
    text: str,
    *,
    size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Cut one document into overlapping windows of `size` words, stepping by `size - overlap`.

    Word windows rather than characters, because a word is the smallest unit that is still readable
    on its own, and rather than sentences, because sentence splitting is a rabbit hole that hides the
    idea on a day whose whole point is the idea. The overlap is what stops a fact that lands on a
    window boundary from being split across two chunks that each only half-contain it.

    A short document produces one chunk; the final window is kept even when it is shorter than
    `size`, because dropping it would silently lose the tail of every document. `overlap` must be
    less than `size`, or the window would never move forward.
    """
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if window:
            chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def chunk_corpus(
    docs: dict[str, str],
    *,
    size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Chunk a whole corpus, tagging every chunk with its source document and position.

    `docs` maps a source name (a filename stem) to the document's full text. The result is the flat
    list of `Chunk`s that gets embedded and stored, in a stable order: documents in the order given,
    chunks within a document in reading order. Stable order matters only so tests and printouts are
    reproducible; nothing downstream depends on it.
    """
    out: list[Chunk] = []
    for source, text in docs.items():
        for ordinal, piece in enumerate(chunk_document(text, size=size, overlap=overlap)):
            out.append(Chunk(source=source, ordinal=ordinal, text=piece))
    return out


def load_corpus(corpus_dir: Union[str, Path], *, suffix: str = ".md") -> dict[str, str]:
    """Read every `*.md` file in a directory into a `{stem: text}` dict, sorted by name.

    The stem (``"refunds.md"`` -> ``"refunds"``) becomes the chunk's `source`, so keeping filenames
    meaningful is what makes a citation readable later. Sorted so the corpus is built the same way
    every time.
    """
    directory = Path(corpus_dir)
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(directory.glob(f"*{suffix}"))
    }


def fastembed_embedder(model_name: str = DEFAULT_MODEL) -> EmbedFn:
    """Build the real embedder: a function from texts to `float32` vectors, backed by fastembed.

    The import is deliberately *inside* this function rather than at module top. Importing
    `fastembed` is what makes ONNX Runtime load, and the first call to the returned function is what
    downloads the model. Keeping both out of module import means this file - and every test that
    imports it - stays fast and offline unless something actually asks to embed real text.

    `TextEmbedding.embed` yields numpy arrays; this normalises them to `float32` so they match what
    the store reads back out of its BLOB column, and returns a list so callers can index into it.
    """
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=model_name)

    def embed(texts: Sequence[str]) -> list[np.ndarray]:
        return [np.asarray(v, dtype=np.float32) for v in model.embed(list(texts))]

    return embed


def _to_blob(vec: np.ndarray) -> bytes:
    """Pack a vector into raw `float32` bytes for a SQLite BLOB column.

    No pickle, no JSON: the bytes of a `float32` array are the most compact and the most honest
    representation, and `numpy.frombuffer` reads them straight back with no copy. This is the entire
    trick behind "a vector store" here - a BLOB column and a convention about its dtype.
    """
    return np.asarray(vec, dtype=np.float32).tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def cosine_scores(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Cosine similarity between each row of `matrix` and the `query` vector.

    Pulled out as a plain function on purpose: it is the one line of real maths in the day, and a
    test can hand it a matrix of `[1,0,0]`-style vectors and check the ranking with no model in
    sight. The zero-vector guards keep an empty or degenerate row from turning the whole result into
    `nan`, which is the kind of silent failure that makes retrieval look broken for no obvious reason.
    """
    if matrix.size == 0:
        return np.empty((0,), dtype=np.float32)
    row_norms = np.linalg.norm(matrix, axis=1)
    query_norm = np.linalg.norm(query)
    safe_rows = np.where(row_norms == 0, 1e-9, row_norms)
    safe_query = query_norm if query_norm else 1e-9
    return (matrix @ query) / (safe_rows * safe_query)


class KnowledgeBase:
    """A tiny vector store over SQLite: chunks in, ranked passages out.

    Everything is one table, `chunks(source, ordinal, text, vec)`, where `vec` is a `float32` BLOB.
    `index()` fills it; `search()` reads it all back, ranks by cosine, and returns the top-k. Holding
    the whole corpus in one numpy matrix per search is not how a production vector database works, and
    that is the point of doing it this way on the fundamentals day: there is no magic index to take on
    faith, just a dot product against every row.

    `db_path=None` uses an in-memory database, which is right for a test or a throwaway build.
    Passing a path writes the vectors to disk, so the corpus is indexed once and reused across
    processes - the same durability story as the checkpointer, in the same kind of file.
    """

    def __init__(self, embed: EmbedFn, *, db_path: Optional[Union[str, Path]] = None):
        self._embed = embed
        self._conn = sqlite3.connect(str(db_path) if db_path else ":memory:")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            "  id INTEGER PRIMARY KEY,"
            "  source TEXT NOT NULL,"
            "  ordinal INTEGER NOT NULL,"
            "  text TEXT NOT NULL,"
            "  vec BLOB NOT NULL"
            ")"
        )
        self._conn.commit()

    def index(self, chunks: Sequence[Chunk]) -> int:
        """Embed a batch of chunks and store their text and vectors. Returns how many were added.

        The embedding happens once, here, in one batched call - not lazily at search time - because
        embedding is the slow step and a query should never pay for it. Re-indexing appends rather
        than replacing, so building the same corpus twice into a file-backed store would duplicate it;
        callers that want a clean rebuild start from a fresh path (see `build`).
        """
        if not chunks:
            return 0
        vectors = self._embed([c.text for c in chunks])
        if len(vectors) != len(chunks):
            raise ValueError("embedder returned a different number of vectors than chunks")
        self._conn.executemany(
            "INSERT INTO chunks (source, ordinal, text, vec) VALUES (?, ?, ?, ?)",
            [(c.source, c.ordinal, c.text, _to_blob(v)) for c, v in zip(chunks, vectors)],
        )
        self._conn.commit()
        return len(chunks)

    def search(self, query: str, *, k: int = 3) -> list[Retrieved]:
        """Return the `k` chunks whose meaning is closest to `query`, most similar first.

        The query is embedded with the *same* function the chunks were, which is the non-negotiable
        part: a query vector and a chunk vector are only comparable because they were produced the
        same way. Everything after that is reading the rows into a matrix and ranking them.

        An empty store returns an empty list rather than raising, because "we have no knowledge about
        this" is a normal answer a caller should be able to handle, not an error.
        """
        rows = self._conn.execute("SELECT source, ordinal, text, vec FROM chunks").fetchall()
        if not rows:
            return []
        matrix = np.stack([_from_blob(vec) for _, _, _, vec in rows])
        query_vec = self._embed([query])[0]
        scores = cosine_scores(matrix, query_vec)
        top = np.argsort(-scores)[:k]
        return [
            Retrieved(
                source=rows[i][0],
                ordinal=rows[i][1],
                text=rows[i][2],
                score=float(scores[i]),
            )
            for i in top
        ]

    def count(self) -> int:
        """How many chunks are stored. Cheap, and handy for a script that says 'indexed N passages'."""
        return int(self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def close(self) -> None:
        self._conn.close()

    @classmethod
    def build(
        cls,
        corpus: Union[str, Path, dict[str, str]],
        embed: EmbedFn,
        *,
        db_path: Optional[Union[str, Path]] = None,
        size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> "KnowledgeBase":
        """Chunk a corpus, embed it, and return a ready-to-search store, in one call.

        `corpus` is either a directory of `*.md` files or an already-loaded `{source: text}` dict, so
        the common script path (point it at `knowledge_base/`) and the common test path (hand it a
        dict) share one entry point. This is the function nearly every caller wants; the pieces are
        exposed separately only so the day can show them one at a time.
        """
        docs = corpus if isinstance(corpus, dict) else load_corpus(corpus)
        kb = cls(embed, db_path=db_path)
        kb.index(chunk_corpus(docs, size=size, overlap=overlap))
        return kb
