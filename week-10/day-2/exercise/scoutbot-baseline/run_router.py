"""Week 9 Day 4 in one script: watch the agent decide *how hard* to retrieve before it retrieves.

Day 3 ran the full formulate-retrieve-critique-reword loop on every ticket, including the ones that
needed no knowledge at all. Today a router runs first and picks a strategy - `direct`, `retrieve`, or
`iterative` - and the graph takes a different path for each. This script runs one ticket per route so
the three paths sit side by side: a thank-you that skips retrieval entirely, a crisp policy question
that searches once, and an oblique question that loops. For each it prints the route the classifier
chose, then one line per pass through the retrieval loop (only the routes that retrieve have any), and
the reply.

    python run_router.py

It builds (or reopens) the same `knowledge.db` as Day 1, so the first run downloads the embedding
model (~130MB) once and is offline after that. The classifier, the query-writing call and the reply
are all real Anthropic calls, so this needs `ANTHROPIC_API_KEY` in the environment (or a .env file).

The contrast is the day. The `direct` ticket makes no retrieval call at all - no query, no search, no
critique - which is latency and a model call saved on a ticket the corpus could never help with. The
`retrieve` ticket searches once and drafts. Only the `iterative` ticket pays for the loop, and it is
the only one that might reword. Adaptive RAG is effort matched to the question.
"""
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import build_ticket_graph, initial_state, thread_config
from scoutbot.knowledge import (
    LOW_CONFIDENCE,
    MAX_RETRIEVAL_ATTEMPTS,
    KnowledgeBase,
    fastembed_embedder,
)

load_dotenv()

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "knowledge_base"
DB_PATH = HERE / "knowledge.db"

# (ticket_id, customer_id, question), one per route we expect the classifier to pick. The first is a
# pure acknowledgement (no policy in it), the second a single clear policy question, the third an
# oblique complaint whose topic is covered but whose wording is a poor first query.
TICKETS = [
    ("T-9401", "1001", "Thanks so much, that's everything I needed - you can close this one!"),
    ("T-9402", "1001", "How long do refunds usually take to come through?"),
    ("T-9403", "1001", "This is the third time I've asked - where is the money you owe me back?"),
]


def _build_or_open_kb() -> KnowledgeBase:
    """Reuse Day 1's persisted index if it exists, build it once if it does not."""
    embed = fastembed_embedder()
    if DB_PATH.exists():
        kb = KnowledgeBase(embed, db_path=DB_PATH)
        if kb.count() > 0:
            print(f"Opened knowledge base: {kb.count()} chunks in {DB_PATH.name}\n")
            return kb
        kb.close()
        DB_PATH.unlink()
    print("Building knowledge base (first run downloads the model, then caches it)...")
    kb = KnowledgeBase.build(CORPUS_DIR, embed, db_path=DB_PATH)
    print(f"Indexed {kb.count()} chunks from {CORPUS_DIR.name}/ into {DB_PATH.name}\n")
    return kb


_ROUTE_BLURB = {
    "direct": "direct (no retrieval)",
    "retrieve": "single retrieval (one search)",
    "iterative": "iterative (search, judge, reword)",
}


def _run_one(graph, ticket_id: str, customer_id: str, question: str) -> None:
    print(f"=== {ticket_id}: {question} ===")
    state = initial_state(question, customer_id, ticket_id)

    draft_pieces: list[str] = []
    route = ""
    query = ""
    best = 0.0
    # One entry per pass through the loop: the query the agent chose, the best score, whether the
    # critique accepted it. A `direct` ticket produces no entries at all, which is exactly the point.
    attempts: list[tuple[str, float, bool]] = []
    for mode, chunk in graph.stream(
        state, thread_config(ticket_id), stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            draft_pieces.append(chunk["draft_chunk"])
        elif "classify_query" in chunk:
            route = chunk["classify_query"]["route"]
        elif "formulate_query" in chunk:
            query = chunk["formulate_query"]["search_query"]
        elif "retrieve_knowledge" in chunk:
            hits = chunk["retrieve_knowledge"]["retrieved"]
            best = hits[0]["score"] if hits else 0.0
        elif "critique_retrieval" in chunk:
            attempts.append((query, best, chunk["critique_retrieval"]["retrieval_ok"]))

    print(f"  route: {_ROUTE_BLURB.get(route, route)}")
    if not attempts:
        print("  retrieval: skipped - answered from courtesy, no search")
    else:
        print("  retrieval loop:")
        for i, (q, score, ok) in enumerate(attempts, start=1):
            if ok:
                verdict = "accepted"
            elif route == "retrieve":
                verdict = f"weak (< {LOW_CONFIDENCE}), but single-retrieval route drafts anyway"
            elif i >= MAX_RETRIEVAL_ATTEMPTS:
                verdict = f"still weak, out of tries (limit {MAX_RETRIEVAL_ATTEMPTS})"
            else:
                verdict = f"weak (< {LOW_CONFIDENCE}), rewording"
            print(f"    try {i}: {q!r} -> best {score:.2f} -> {verdict}")
    print(f"  reply: {''.join(draft_pieces).strip()}\n")


def main() -> None:
    kb = _build_or_open_kb()
    # The knowledge base is bound into the graph exactly as the ledger is; `classify=None` and
    # `formulate=None` leave the real model calls in place. The tests inject fakes for both.
    graph = build_ticket_graph(kb=kb)
    for ticket_id, customer_id, question in TICKETS:
        _run_one(graph, ticket_id, customer_id, question)
    kb.close()


if __name__ == "__main__":
    main()
