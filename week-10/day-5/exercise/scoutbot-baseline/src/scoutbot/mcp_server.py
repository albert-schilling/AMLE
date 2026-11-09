"""ScoutBot as an MCP *server*: Week 10 Day 2 turns the day around.

Yesterday ScoutBot was a client - it discovered and called a tool another team published. Today it
is the other side of the same protocol: ScoutBot exposes *its own* capabilities as MCP tools, so any
client that speaks the protocol can use them. The support bot stops being a closed application and
becomes a piece of reusable infrastructure.

Two of ScoutBot's existing capabilities are published, unchanged underneath:

- `search_policy(query, k)` wraps the `KnowledgeBase` retrieval built in Week 9 - the same
  embed-store-cosine search, now reachable over MCP by anyone, returning each passage's source, text
  and score.
- `look_up_customer(customer_id)` wraps the exact function the native tool already calls (see
  `tools.look_up_customer`). Note that this same capability now exists *twice*: as a hand-wired native
  tool inside our loop, and as an MCP tool any external client can call. Publishing it did not require
  rewriting it.

**The type hints are the schema.** Each tool is a plain typed function decorated `@mcp.tool()`, and
`FastMCP` derives the JSON schema from the annotations - no hand-written `input_schema` dict, in
deliberate contrast to `tools.py`. That is the whole ergonomic win of writing a server this way.

**The knowledge base is injected, exactly like everywhere else in this codebase.** `build_server(kb=...)`
takes an optional `KnowledgeBase` (or any object with a `.search(query, k=...)` method). Passing one is
how the offline tests reach `search_policy` without downloading an embedding model - the same
"inject the collaborator that needs the network" discipline the graph nodes use. Left as `None`, the
server lazily builds/opens the process-wide `knowledge.db` on first use, exactly as the Week 9 demos do.

Run it directly to serve over stdio (how `run_mcp_server.py` and real MCP hosts launch it):

    python scoutbot_mcp_server.py

Or inspect it interactively with the MCP Inspector:

    mcp dev scoutbot_mcp_server.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .knowledge import KnowledgeBase, fastembed_embedder
from .tools import look_up_customer as _look_up_customer

ROOT = Path(__file__).parent.parent.parent
CORPUS_DIR = ROOT / "knowledge_base"
DB_PATH = ROOT / "knowledge.db"

# Lazily built the first time `search_policy` runs without an injected kb. Process-wide, so a
# long-running server embeds the corpus once, and cheap to leave None at import (no model load).
_PROCESS_KB: Optional[KnowledgeBase] = None


def _process_kb() -> KnowledgeBase:
    """Build or reopen the shared knowledge base, downloading the embedding model once on first use."""
    global _PROCESS_KB
    if _PROCESS_KB is None:
        embed = fastembed_embedder()
        if DB_PATH.exists():
            kb = KnowledgeBase(embed, db_path=DB_PATH)
            _PROCESS_KB = kb if kb.count() > 0 else KnowledgeBase.build(CORPUS_DIR, embed, db_path=DB_PATH)
        else:
            _PROCESS_KB = KnowledgeBase.build(CORPUS_DIR, embed, db_path=DB_PATH)
    return _PROCESS_KB


def build_server(kb: Optional[Any] = None) -> FastMCP:
    """Assemble the ScoutBot tool server. Pass a `kb` (anything with `.search(query, k=...)`) to keep
    `search_policy` offline in tests; leave it `None` to lazily build the real knowledge base."""
    mcp = FastMCP("scoutbot-tools")

    @mcp.tool()
    def search_policy(query: str, k: int = 3) -> list[dict]:
        """Search Anchorpoint's support-policy knowledge base for passages relevant to a query.

        Returns up to k passages, best match first, each with its source document, its text, and a
        cosine relevance score (roughly 0..1; a low top score means the corpus likely has no answer).
        """
        knowledge = kb if kb is not None else _process_kb()
        return [
            {"source": hit.source, "text": hit.text, "score": round(hit.score, 4)}
            for hit in knowledge.search(query, k=k)
        ]

    @mcp.tool()
    def look_up_customer(customer_id: str) -> dict:
        """Look up an existing customer's account by customer_id (read-only, no side effects).

        Returns the customer's plan, account age, and recent refund history, or {"found": false, ...}
        if the id is unknown. This publishes the exact capability the native look_up_customer tool
        already provides, now reachable by any MCP client.
        """
        return _look_up_customer(customer_id)

    return mcp


# Module-level instance for the stdio entrypoint (`scoutbot_mcp_server.py`). Tools bind the lazy
# process kb; tests build their own server with an injected kb instead of using this one.
mcp = build_server()
