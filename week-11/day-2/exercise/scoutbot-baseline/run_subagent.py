"""Week 10 Day 3, the subagent half in one script: delegate a scoped question, get a contract back.

ScoutBot hands a self-contained policy question to a research subagent and receives one thing: a
validated `ResearchResult` - an answer, its sources, and a confidence score. The parent never sees the
subagent's internal steps (the retrieval, the reading); it depends only on the shape of what comes
back. That shape is the contract, and it is what makes delegating safe.

Runs offline apart from the one-time embedding-model download the first policy search triggers (the
same `knowledge.db` the other demos build). The synthesis step here is the deterministic
`passage_synthesize`; a production subagent would put a model there, returning the same contracted
shape.

    python run_subagent.py
"""
from pathlib import Path

from scoutbot.knowledge import KnowledgeBase, fastembed_embedder
from scoutbot.subagent import ResearchSubagent

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "knowledge_base"
DB_PATH = HERE / "knowledge.db"

QUESTIONS = [
    "How long does a refund take to arrive?",
    "Can I get a refund after 60 days?",
]


def main():
    embed = fastembed_embedder()
    if DB_PATH.exists() and KnowledgeBase(embed, db_path=DB_PATH).count() > 0:
        kb = KnowledgeBase(embed, db_path=DB_PATH)
    else:
        kb = KnowledgeBase.build(CORPUS_DIR, embed, db_path=DB_PATH)

    subagent = ResearchSubagent(kb=kb)

    for question in QUESTIONS:
        result = subagent.run(question)
        print(f"Q: {question}")
        print(f"   answer:     {result['answer'][:100]}")
        print(f"   sources:    {result['sources']}")
        print(f"   confidence: {result['confidence']}")
        if result["confidence"] < 0.4:
            print("   (low confidence - ScoutBot should hedge or escalate rather than state this flatly)")
        print()

    print("The parent only ever saw these three fields - the subagent's steps stayed inside it.")


if __name__ == "__main__":
    main()
