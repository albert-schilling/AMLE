"""Saved workflow runs: the SQLite checkpointer, one thread per ticket, its status."""

import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import StateSnapshot

from .models import (
    Customer,
    Escalated,
    KnowledgePassage,
    NotEscalated,
    Ticket,
    TicketClassification,
)

# State types saved in checkpoints; only these (and safe built-ins) load back.
# A missing one does not fail: it loads back as a plain dict, with a warning.
CHECKPOINT_TYPES = [
    Customer,
    Escalated,
    KnowledgePassage,
    NotEscalated,
    Ticket,
    TicketClassification,
]
CHECKPOINT_SERDE = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)

RunStatus = Literal["new", "paused", "unfinished", "finished"]


@contextmanager
def open_checkpointer(path: Path) -> Generator[SqliteSaver]:
    """Open the SQLite file at ``path`` (created if missing) and close it after use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, check_same_thread=False)) as connection:
        yield SqliteSaver(connection, serde=CHECKPOINT_SERDE)


def thread_config(ticket_id: str) -> RunnableConfig:
    """Each ticket is its own thread, so its checkpoints are stored under its id."""
    return {"configurable": {"thread_id": ticket_id}}


def run_status(saved: StateSnapshot) -> RunStatus:
    """Where a ticket's saved thread stands.

    ``next`` holds the nodes left to run. A paused run has ``next`` set too, so the
    interrupt check must come first.
    """
    if saved.interrupts:
        return "paused"  # waits for a human answer
    if saved.next:
        return "unfinished"  # nodes left, nobody waiting: the run stopped midway
    if saved.values:
        return "finished"  # reached END
    return "new"  # nothing saved yet
