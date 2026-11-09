"""Week 9 Day 5 in one script: watch the bot stop being a stranger to a returning customer.

Every earlier day made a single *ticket* smarter - it retrieves, grounds, loops, routes - but each run
still began from nothing, so a customer who wrote in an hour ago was a stranger now. Today the graph
gains a person-shaped memory. `recall_memory` runs right after the customer lookup and pulls this
customer's relevant past tickets out of a `MemoryStore`; `write_memory` runs last and records the
finished ticket, keyed so it is remembered exactly once. This script sends a small run of tickets and
prints, for each, what the bot *recalled* before drafting and what it *wrote* after - so you can watch
the second ticket from a customer arrive with the first already in front of it.

    python run_memory.py

Three things are worth watching:

- **Continuity.** The first ticket from customer 1001 recalls nothing. The second, from the same
  customer, recalls the first and drafts with it as background - the whole point of the day.
- **Scope.** A third customer asking a *similar* question recalls nothing, because memory is filtered
  by `customer_id`: one person's history is structurally invisible to another's.
- **Persistence.** Memory is written to `memory.db`. Run the script a second time and 1001's very
  first ticket now recalls what the first run remembered - memory that outlives the process, the same
  durability the checkpointer gives a run and the ledger gives a send.

It reuses Day 1's `knowledge.db` for grounding and the *same* embedder for memory, so the first run
downloads the embedding model (~130MB) once and is offline after. Triage, routing, query-writing and
the reply are real Anthropic calls, so this needs `ANTHROPIC_API_KEY` in the environment (or a .env).
"""
from pathlib import Path

from dotenv import load_dotenv

from scoutbot import build_ticket_graph, initial_state, thread_config
from scoutbot.knowledge import KnowledgeBase, fastembed_embedder
from scoutbot.memory import MemoryStore

load_dotenv()

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "knowledge_base"
KB_PATH = HERE / "knowledge.db"
MEMORY_PATH = HERE / "memory.db"

# A scripted contact history, in order. The first two are the same customer (1001) writing twice about
# the same billing thread, so the second should recall the first. The third is a *different* customer
# (2002) asking a similar question, there to show recall is scoped to a person and finds nothing of
# theirs. All three are low-stakes informational questions, so each finishes and writes its memory
# rather than pausing for a human.
TICKETS = [
    ("T-5001", "1001", "Hi - where in my account do I find my past invoices to download?"),
    ("T-5002", "1001", "Thanks! And can I export those same invoices to a CSV file?"),
    ("T-5003", "2002", "Where can I download my invoices from my account?"),
]


def _build_or_open_kb() -> KnowledgeBase:
    """Reuse Day 1's persisted index if it exists, build it once if it does not."""
    embed = fastembed_embedder()
    if KB_PATH.exists():
        kb = KnowledgeBase(embed, db_path=KB_PATH)
        if kb.count() > 0:
            print(f"Opened knowledge base: {kb.count()} chunks in {KB_PATH.name}")
            return kb, embed
        kb.close()
        KB_PATH.unlink()
    print("Building knowledge base (first run downloads the model, then caches it)...")
    kb = KnowledgeBase.build(CORPUS_DIR, embed, db_path=KB_PATH)
    print(f"Indexed {kb.count()} chunks from {CORPUS_DIR.name}/ into {KB_PATH.name}")
    return kb, embed


def _run_one(graph, ticket_id: str, customer_id: str, question: str) -> None:
    print(f"\n=== {ticket_id} (customer {customer_id}): {question} ===")
    state = initial_state(question, customer_id, ticket_id)

    recalled: list[dict] = []
    wrote_note = ""
    draft_pieces: list[str] = []
    paused = False
    for mode, chunk in graph.stream(
        state, thread_config(ticket_id), stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            draft_pieces.append(chunk["draft_chunk"])
        elif "recall_memory" in chunk:
            recalled = chunk["recall_memory"]["recalled"]
        elif "write_memory" in chunk:
            wrote_note = chunk["write_memory"]["notes"][-1]
        elif "__interrupt__" in chunk:
            paused = True

    if recalled:
        print(f"  recalled {len(recalled)} past ticket(s) for this customer:")
        for m in recalled:
            print(f"    - (ticket {m['ticket_id']}, score {m['score']:.2f}) {m['text']}")
    else:
        print("  recalled: nothing on file for this customer")

    print(f"  reply: {''.join(draft_pieces).strip()}")
    if paused:
        # A ticket that needs a human stops before write_memory; the demo's tickets are chosen not to,
        # but say so honestly if one does rather than printing a misleading blank.
        print("  memory: not written - this ticket paused for a human before it finished")
    else:
        print(f"  memory: {wrote_note}")


def main() -> None:
    kb, embed = _build_or_open_kb()
    # Memory reuses the *same* embedder as the corpus - no second model - and persists to its own file,
    # bound into the graph exactly as `kb` is. Delete memory.db to start the customer history over.
    memory = MemoryStore(embed, db_path=MEMORY_PATH)
    print(
        f"Opened memory: {memory.count()} memories on file "
        f"({memory.count('1001')} for customer 1001)"
    )

    graph = build_ticket_graph(kb=kb, memory=memory)
    for ticket_id, customer_id, question in TICKETS:
        _run_one(graph, ticket_id, customer_id, question)

    print(
        f"\nMemory now holds {memory.count()} total "
        f"({memory.count('1001')} for 1001, {memory.count('2002')} for 2002). "
        f"Run again and 1001's first ticket will recall this run."
    )
    kb.close()
    memory.close()


if __name__ == "__main__":
    main()
