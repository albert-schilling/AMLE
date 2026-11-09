"""Week 9 Day 3 in one script: watch the agent search, judge what it found, and search again.

Day 2 retrieved once, on the raw ticket text, and drafted from whatever came back. Today retrieval is
a loop the agent drives. It turns the ticket into a *query* (the policy topic underneath the venting),
looks that up, and critiques the result: if the best passage is too weak to trust, it rewords the
query and tries again, up to `MAX_RETRIEVAL_ATTEMPTS`. This script prints one line per attempt so the
loop is visible - the query the agent chose, the best score it got back, and the critique's verdict -
and then the reply it finally drafts.

    python run_agentic.py

It builds (or reopens) the same `knowledge.db` as Day 1, so the first run downloads the embedding
model (~130MB) once and is offline after that. Both the query the agent writes and the reply it
streams are real Anthropic calls, so this needs `ANTHROPIC_API_KEY` in the environment (or a .env
file).

Two tickets, chosen to show both exits of the loop. The first is answerable but obliquely worded, so
the value is in the agent naming the topic rather than searching the complaint verbatim. The second is
genuinely outside the corpus, so the loop rewords, exhausts its attempts, and the grounded draft
declines rather than inventing a figure. Watch the attempt count on the second one stop at the bound
instead of spinning.
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

# (ticket_id, customer_id, question). The first is answerable but worded as a complaint, so the win is
# the agent naming the topic. The second is off-topic on purpose: the corpus has nothing about import
# duties, so the loop should reword, hit its attempt bound, and the reply should decline.
TICKETS = [
    ("T-9301", "1001", "This is the third time I've asked - where is the money you owe me back?"),
    ("T-9302", "1001", "What import duties will I owe if it ships from outside the EU?"),
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


def _run_one(graph, ticket_id: str, customer_id: str, question: str) -> None:
    print(f"=== {ticket_id}: {question} ===")
    state = initial_state(question, customer_id, ticket_id)

    draft_pieces: list[str] = []
    # One entry per pass through the loop: the query the agent chose, the best score it retrieved for
    # it, and whether the critique accepted it. `updates` carries each node's return; `custom` carries
    # the draft chunks as the model writes them.
    query = ""
    best = 0.0
    attempts: list[tuple[str, float, bool]] = []
    for mode, chunk in graph.stream(
        state, thread_config(ticket_id), stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            draft_pieces.append(chunk["draft_chunk"])
        elif "formulate_query" in chunk:
            query = chunk["formulate_query"]["search_query"]
        elif "retrieve_knowledge" in chunk:
            hits = chunk["retrieve_knowledge"]["retrieved"]
            best = hits[0]["score"] if hits else 0.0
        elif "critique_retrieval" in chunk:
            attempts.append((query, best, chunk["critique_retrieval"]["retrieval_ok"]))

    print("  retrieval loop:")
    for i, (q, score, ok) in enumerate(attempts, start=1):
        if ok:
            verdict = "accepted"
        elif i >= MAX_RETRIEVAL_ATTEMPTS:
            verdict = f"still weak, out of tries (limit {MAX_RETRIEVAL_ATTEMPTS})"
        else:
            verdict = f"weak (< {LOW_CONFIDENCE}), rewording"
        print(f"    try {i}: {q!r} -> best {score:.2f} -> {verdict}")
    print(f"  grounded reply: {''.join(draft_pieces).strip()}\n")


def main() -> None:
    kb = _build_or_open_kb()
    # The knowledge base is bound into the graph exactly as the ledger is, and `formulate=None` leaves
    # the real query-writing model call in place; the tests are the ones that inject a fake for it.
    graph = build_ticket_graph(kb=kb)
    for ticket_id, customer_id, question in TICKETS:
        _run_one(graph, ticket_id, customer_id, question)
    kb.close()


if __name__ == "__main__":
    main()
