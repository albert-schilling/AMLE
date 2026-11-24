"""Measure search quality on labelled questions, and compare chunk settings.

A passage answers a question if it comes from the labelled document and contains the
labelled phrase. Only answerable questions count towards the scores.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from pydantic import TypeAdapter

from ..models import EvalQuestion, KnowledgePassage
from .store import KnowledgeBase

QUESTIONS = TypeAdapter(list[EvalQuestion])
TOP_K = 3  # passages searched per question, like knowledge_top_k

Search = Callable[[str, int], list[KnowledgePassage]]  # (query, k) -> passages


@dataclass(frozen=True)
class SearchQuality:
    """Share of answerable questions answered by the first passage, or by any of the
    top three, and the mean reciprocal rank of the first answer (0 if none)."""

    hit_at_1: float
    hit_at_3: float
    mean_reciprocal_rank: float


@dataclass(frozen=True)
class ChunkSettingResult:
    chunk_size: int
    chunk_overlap: int
    chunk_count: int
    vector: SearchQuality  # embeddings, cosine similarity
    keyword: SearchQuality  # PostgreSQL full-text search


def load_questions(path: Path) -> list[EvalQuestion]:
    return QUESTIONS.validate_json(path.read_bytes())


def normalize(text: str) -> str:
    """Single spaces: chunks join their words that way, documents wrap lines."""
    return " ".join(text.split())


def answers(question: EvalQuestion, passage: KnowledgePassage) -> bool:
    """Whether ``passage`` holds the labelled answer to ``question``."""
    if question.source is None or question.answer is None:
        return False
    return passage.source == question.source and normalize(
        question.answer
    ) in normalize(passage.text)


def answer_rank(question: EvalQuestion, passages: Sequence[KnowledgePassage]) -> int:
    """Position of the first answering passage, from 1; 0 if none answers."""
    for rank, passage in enumerate(passages, start=1):
        if answers(question, passage):
            return rank
    return 0


def measure(search: Search, questions: Sequence[EvalQuestion]) -> SearchQuality:
    answerable = [question for question in questions if question.answerable]
    if not answerable:
        raise ValueError("no answerable questions to measure")
    ranks = [
        answer_rank(question, search(question.question, TOP_K))
        for question in answerable
    ]
    return SearchQuality(
        hit_at_1=sum(rank == 1 for rank in ranks) / len(ranks),
        hit_at_3=sum(rank > 0 for rank in ranks) / len(ranks),
        mean_reciprocal_rank=sum(1 / rank for rank in ranks if rank) / len(ranks),
    )


def compare_chunk_settings(
    knowledge: KnowledgeBase,
    docs: dict[str, str],
    questions: Sequence[EvalQuestion],
    settings: Sequence[tuple[int, int]],
) -> list[ChunkSettingResult]:
    """Build an index per (size, overlap), unless unchanged, and measure vector and
    keyword search on each one.

    Every setting keeps its own index, so a later run reuses them.
    """
    results = []
    for size, overlap in settings:
        variant = replace(knowledge, chunk_size=size, chunk_overlap=overlap)
        build = variant.build(docs)
        results.append(
            ChunkSettingResult(
                size,
                overlap,
                build.chunk_count,
                vector=measure(variant.search, questions),
                keyword=measure(variant.keyword_search, questions),
            )
        )
    return results


def results_table(results: Sequence[ChunkSettingResult]) -> str:
    """A Markdown table, best vector mean reciprocal rank first."""
    rows = [
        "| Size | Overlap | Chunks | Vector Hit@1 | Hit@3 | MRR "
        "| Keyword Hit@1 | Hit@3 | MRR |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    ranked = sorted(results, key=lambda r: r.vector.mean_reciprocal_rank, reverse=True)
    for r in ranked:
        rows.append(
            f"| {r.chunk_size} | {r.chunk_overlap} | {r.chunk_count} "
            f"| {quality_cells(r.vector)} | {quality_cells(r.keyword)} |"
        )
    return "\n".join(rows)


def quality_cells(q: SearchQuality) -> str:
    return f"{q.hit_at_1:.2f} | {q.hit_at_3:.2f} | {q.mean_reciprocal_rank:.2f}"
