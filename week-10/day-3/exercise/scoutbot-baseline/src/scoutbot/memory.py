"""ScoutBot's memory: what it remembers about a customer *across* tickets, not just within one run.

This is Week 9 Day 5, and it is the last idea the week is missing. Every day so far made a *single*
ticket smarter - retrieve, ground, loop, route - but each run still started from nothing. A customer who
wrote in last week is a stranger this week: the checkpointer remembers a run, and nothing remembers a
*person*. This module is the person-shaped memory. It stores a short line about each finished ticket,
keyed by `customer_id`, and lets the next ticket from that customer recall the relevant ones before it
drafts.

**Knowledge and memory are the same machinery pointed at different things, and the contrast is the day.**
`knowledge.py` holds one shared, static corpus - the policies, the same for every customer - and answers
"what does our policy say?". This module holds many small, growing, *per-customer* records - what this
one person has contacted us about - and answers "what do we already know about them?". Knowledge is
retrieved and cited as a source; memory is recalled as background and never cited. One is what the
company knows; the other is what it remembers about you.

The store deliberately reuses Day 1's parts rather than inventing new ones, so the new idea is the
*scope*, not the mechanics:

- **The same embedder.** A memory is embedded with the same `EmbedFn` the knowledge base uses, so
  "where is my refund" recalls a past "my refund never arrived" even though they share few words. Memory
  recall is semantic search, exactly like retrieval; it is just searching a different, smaller,
  customer-scoped table.
- **The same vector-in-SQLite trick.** Memories live as `float32` BLOBs in one table, next to the
  chunks, the checkpoints and the ledger. A `customer_id` column is the only structural difference from
  `KnowledgeBase`, and `recall` filters on it so one customer never sees another's history. That column
  is the whole of "cross-thread, per-customer".
- **An idempotency guard, echoing Week 8.** `write` is keyed on `ticket_id`: writing the same ticket's
  memory twice stores it once. A run that is resumed, or a ticket handled again, must not pile up
  duplicate memories, the same "acting once" discipline the send-ledger taught, applied to remembering
  once.

**Why the embedder is injected**, same as `KnowledgeBase`: `MemoryStore` takes an `embed` function and
never reaches for a model itself, so a test hands it fixed vectors and checks recall with no download and
no network. In real use it is the shared `fastembed_embedder()`; there is no reason to load a second
model for memory when the one the corpus uses embeds a sentence just as well.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union

import numpy as np

from .knowledge import EmbedFn, _from_blob, _to_blob, cosine_scores

MEMORY_RELEVANCE = 0.3
"""Below this cosine score, a past memory is treated as unrelated to the new ticket and left out.

Lower than `knowledge.LOW_CONFIDENCE` (0.5) on purpose, and the difference is a judgement worth making
out loud. A weak *retrieval* is dangerous - it grounds a factual reply, so a near-miss passage can put a
wrong number in front of a customer, and the floor is set high to keep it out. A weak *recall* is cheap -
it only adds background context to a draft a human still reviews, so surfacing a loosely-related past
ticket costs little and skipping a relevant one costs more. Memory errs toward remembering; retrieval
errs toward silence.
"""


@dataclass(frozen=True)
class Recalled:
    """A past memory that matched the current ticket, and how strongly it matched.

    `text` is the line that was stored when an earlier ticket finished; `ticket_id` is which ticket it
    came from, so a draft (or a person reading the run) can trace a recalled fact back to its origin; and
    `score` is cosine similarity to the current ticket, the same 0..1 scale retrieval uses. Surfaced
    rather than hidden because a recalled memory with a middling score is background worth showing to a
    reviewer, not a fact to state as certain.
    """

    ticket_id: str
    text: str
    score: float


def format_memories(memories: Sequence[Union[Recalled, dict]]) -> str:
    """Render recalled memories as the background block a draft prompt receives.

    Each memory becomes one bulleted line, `- (ticket T-1001) asked about a late refund...`, tagged with
    its ticket so a reviewer can trace it. Deliberately unlike `knowledge.format_passages`: no
    `[source]` tag, because memory is background the model may *use* but must not *cite* - the citation
    shape is reserved for policy passages, and a memory dressed as a citation is exactly the confusion to
    avoid. Accepts either `Recalled` objects (what `recall` returns) or the plain dicts the graph keeps
    in state, so the memory a test asserts on is the memory the model is sent.
    """
    def field(memory: Union[Recalled, dict], name: str) -> str:
        return memory[name] if isinstance(memory, dict) else getattr(memory, name)

    return "\n".join(
        f"- (ticket {field(m, 'ticket_id')}) {field(m, 'text')}" for m in memories
    )


class MemoryStore:
    """A per-customer memory over SQLite: a line in when a ticket finishes, the relevant lines out
    when the next one starts.

    One table, `memories(customer_id, ticket_id, text, vec, ts)`, where `vec` is a `float32` BLOB and
    `ts` is a write timestamp kept only so a store can be inspected in time order. It is `KnowledgeBase`
    with two differences that carry the whole idea: every row is tagged with a `customer_id` that
    `recall` filters on, so memory is *scoped to a person*; and `write` is keyed on `ticket_id` so a
    ticket is remembered exactly once however many times its run executes.

    `db_path=None` uses an in-memory database, right for a test or a throwaway. Passing a path persists
    the memories, so what ScoutBot learned about a customer last week is still there this week - the
    durability story is the checkpointer's and the ledger's, applied to memory, and pointed at the same
    kind of file.
    """

    def __init__(self, embed: EmbedFn, *, db_path: Optional[Union[str, Path]] = None):
        self._embed = embed
        # `check_same_thread=False` for the same reason the knowledge base and the checkpointer need it:
        # once this store is a node in a graph, LangGraph may run that node on a worker thread, which is
        # not the thread that opened the connection.
        self._conn = sqlite3.connect(
            str(db_path) if db_path else ":memory:", check_same_thread=False
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "  id INTEGER PRIMARY KEY,"
            "  customer_id TEXT NOT NULL,"
            "  ticket_id TEXT NOT NULL,"
            "  text TEXT NOT NULL,"
            "  vec BLOB NOT NULL,"
            "  ts REAL NOT NULL"
            ")"
        )
        self._conn.commit()

    def write(self, customer_id: str, ticket_id: str, text: str) -> bool:
        """Remember one finished ticket for one customer. Returns whether a new memory was stored.

        Keyed on `ticket_id`: if this customer already has a memory for this ticket, nothing is written
        and this returns `False`. That guard is the same discipline as the send-ledger from Week 8, and
        it is here for the same reason - the write node runs at the end of a graph that can be resumed or
        re-run, and a memory store that grew a duplicate every time a run replayed would slowly poison
        recall with the same line five times over. Remembering, like sending, must happen once per ticket
        no matter how often the code executes.

        The text is embedded once, on write, with the same function the corpus uses, so recall never pays
        to embed a stored memory - only the incoming ticket is embedded at recall time.
        """
        existing = self._conn.execute(
            "SELECT 1 FROM memories WHERE customer_id = ? AND ticket_id = ?",
            (customer_id, ticket_id),
        ).fetchone()
        if existing is not None:
            return False
        vec = self._embed([text])[0]
        self._conn.execute(
            "INSERT INTO memories (customer_id, ticket_id, text, vec, ts) VALUES (?, ?, ?, ?, ?)",
            (customer_id, ticket_id, text, _to_blob(vec), time.time()),
        )
        self._conn.commit()
        return True

    def recall(
        self,
        customer_id: str,
        query: str,
        *,
        k: int = 3,
        min_score: float = MEMORY_RELEVANCE,
    ) -> list[Recalled]:
        """Return up to `k` of this customer's past memories most similar to `query`, best first.

        Two things make this memory rather than retrieval, and both are in the SQL and the filter. The
        query only ever loads *this customer's* rows (`WHERE customer_id = ?`), so one person's history is
        structurally invisible to another's - the privacy property is a where-clause, not a policy. And a
        memory below `min_score` is dropped rather than returned, because unlike retrieval, which must
        return its best guess so the critique can judge it, recall would rather surface nothing than pad a
        draft with an unrelated past ticket.

        A customer with no history, or none relevant, gets an empty list - the normal case for a
        first-time contact, and one the caller must handle as "no memory" rather than an error.
        """
        rows = self._conn.execute(
            "SELECT ticket_id, text, vec FROM memories WHERE customer_id = ?",
            (customer_id,),
        ).fetchall()
        if not rows:
            return []
        matrix = np.stack([_from_blob(vec) for _, _, vec in rows])
        query_vec = self._embed([query])[0]
        scores = cosine_scores(matrix, query_vec)
        order = np.argsort(-scores)
        recalled = []
        for i in order[:k]:
            score = float(scores[i])
            if score < min_score:
                continue
            recalled.append(Recalled(ticket_id=rows[i][0], text=rows[i][1], score=score))
        return recalled

    def count(self, customer_id: Optional[str] = None) -> int:
        """How many memories are stored, in total or for one customer. Handy for a demo's status line."""
        if customer_id is None:
            return int(self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE customer_id = ?", (customer_id,)
            ).fetchone()[0]
        )

    def close(self) -> None:
        self._conn.close()
