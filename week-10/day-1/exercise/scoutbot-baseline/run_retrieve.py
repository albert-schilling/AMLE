"""Build ScoutBot's knowledge base from `knowledge_base/`, then retrieve against a few questions.

This is the day in one script. It does no model reasoning and sends nothing to a customer: it chunks
the policy documents, embeds them once, stores the vectors in `knowledge.db`, and then shows which
passages come back for a handful of real support questions - and, deliberately, one question the
corpus has no answer to, so the scores for a miss are visible next to the scores for a hit.

    python run_retrieve.py

The first run downloads the embedding model (~130MB) once; after that it is fully offline. Delete
`knowledge.db` to force a clean rebuild.
"""
from pathlib import Path

from scoutbot.knowledge import KnowledgeBase, fastembed_embedder

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "knowledge_base"
DB_PATH = HERE / "knowledge.db"

QUESTIONS = [
    "How long does a refund take to reach my account?",
    "Do I pay for shipping on a 30 euro order?",
    "My headphones stopped charging after six months, are they covered?",
    "Why was I charged twice for one order?",
    "What is the capital of France?",  # not in the corpus, on purpose
]


def _build_or_open() -> KnowledgeBase:
    embed = fastembed_embedder()
    if DB_PATH.exists():
        kb = KnowledgeBase(embed, db_path=DB_PATH)
        if kb.count() > 0:
            print(f"Opened existing knowledge base: {kb.count()} chunks in {DB_PATH.name}\n")
            return kb
        kb.close()
        DB_PATH.unlink()
    print("Building knowledge base (first run downloads the model, then caches it)...")
    kb = KnowledgeBase.build(CORPUS_DIR, embed, db_path=DB_PATH)
    print(f"Indexed {kb.count()} chunks from {CORPUS_DIR.name}/ into {DB_PATH.name}\n")
    return kb


def main() -> None:
    kb = _build_or_open()
    for question in QUESTIONS:
        print(f"Q: {question}")
        hits = kb.search(question, k=2)
        for rank, hit in enumerate(hits, start=1):
            snippet = hit.text if len(hit.text) <= 90 else hit.text[:87] + "..."
            print(f"   {rank}. [{hit.source} #{hit.ordinal}] score={hit.score:.3f}  {snippet}")
        best = hits[0].score if hits else 0.0
        if best < 0.5:
            print("   (top score is low - the corpus probably does not answer this)")
        print()
    kb.close()


if __name__ == "__main__":
    main()
