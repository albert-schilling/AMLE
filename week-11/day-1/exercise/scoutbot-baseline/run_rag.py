"""Week 9 Day 2 in one script: retrieve, then draft an answer grounded in what was retrieved.

Where `run_retrieve.py` (Day 1) stopped at "here are the passages that match", this runs the whole
graph and shows the reply the model writes *from* those passages - with the source cited in brackets,
and, for a question the corpus does not cover, a refusal instead of a guess. The contrast is the point
of the day: the same model that invented "three to five days" last week now either cites a policy or
says a teammate will follow up.

    python run_rag.py

It builds (or reopens) the same `knowledge.db` as Day 1, so the first run downloads the embedding
model (~130MB) once and is offline after that. The draft itself is a real streamed Anthropic call, so
this needs `ANTHROPIC_API_KEY` in the environment (or a .env file) - unlike `run_retrieve.py`, which
sends nothing to a model at all.

Three tickets, on purpose: two the policies answer and one they do not, so a grounded reply and a
grounded refusal sit next to each other. Watch the `[source]` tags in the reply line up with the
passages printed above it.
"""
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import build_ticket_graph, initial_state, thread_config
from scoutbot.knowledge import LOW_CONFIDENCE, KnowledgeBase, fastembed_embedder

load_dotenv()

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "knowledge_base"
DB_PATH = HERE / "knowledge.db"

# (ticket_id, customer_id, question). The last one is off-topic on purpose: the corpus has nothing
# about international duties, so the reply should decline rather than invent a figure.
TICKETS = [
    ("T-9201", "1001", "How long does a refund take to reach my account?"),
    ("T-9202", "1002", "Do I have to pay for shipping on a thirty euro order?"),
    ("T-9203", "1001", "What import duties will I owe if it ships from outside the EU?"),
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
    retrieved: list[dict] = []
    # `custom` carries the draft's chunks as the model writes them; `updates` carries each node's
    # return, which is where the retrieved passages surface.
    for mode, chunk in graph.stream(
        state, thread_config(ticket_id), stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            draft_pieces.append(chunk["draft_chunk"])
        elif "retrieve_knowledge" in chunk:
            retrieved = chunk["retrieve_knowledge"]["retrieved"]

    best = retrieved[0]["score"] if retrieved else 0.0
    flag = "  <- low confidence, expect a refusal" if best < LOW_CONFIDENCE else ""
    print("  retrieved:")
    for passage in retrieved:
        snippet = passage["text"]
        snippet = snippet if len(snippet) <= 70 else snippet[:67] + "..."
        print(f"    [{passage['source']}] {passage['score']:.2f}  {snippet}")
    print(f"  best score: {best:.2f}{flag}")
    print(f"  grounded reply: {''.join(draft_pieces).strip()}\n")


def main() -> None:
    kb = _build_or_open_kb()
    # The knowledge base is bound into the graph the same way the ledger is: one object, reused for
    # every ticket, injected rather than reached for.
    graph = build_ticket_graph(kb=kb)
    for ticket_id, customer_id, question in TICKETS:
        _run_one(graph, ticket_id, customer_id, question)
    kb.close()


if __name__ == "__main__":
    main()
