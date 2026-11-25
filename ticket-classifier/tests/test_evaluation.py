from pathlib import Path

import pytest
from helpers import FakeKnowledge, KeywordEmbedder
from pydantic import ValidationError

from ticket_classifier.config import get_settings
from ticket_classifier.knowledge.documents import load_documents
from ticket_classifier.knowledge.evaluation import (
    ChunkSettingResult,
    SearchQuality,
    answer_rank,
    answers,
    compare_chunk_settings,
    compare_thresholds,
    load_questions,
    measure,
    normalize,
    results_table,
)
from ticket_classifier.knowledge.store import KnowledgeBase, create_schema
from ticket_classifier.models import EvalQuestion, KnowledgePassage

PROJECT = Path(__file__).parent.parent
QUESTIONS_PATH = PROJECT / "data/eval/knowledge_questions.json"


def passage(source, text):
    return KnowledgePassage(source=source, ordinal=0, text=text, score=0.8)


def question(source="refunds.md", answer="within 30 days"):
    return EvalQuestion(id="Q-1", question="?", source=source, answer=answer)


def test_every_answer_phrase_is_in_its_document_once():
    docs = load_documents(PROJECT / get_settings().knowledge_base_path)

    for q in load_questions(QUESTIONS_PATH):
        if q.answerable:
            assert normalize(docs[q.source]).count(normalize(q.answer)) == 1, q.id


def test_question_set_has_unique_ids_and_unanswerable_questions():
    questions = load_questions(QUESTIONS_PATH)

    assert len({q.id for q in questions}) == len(questions)
    assert any(not q.answerable for q in questions)


def test_source_without_answer_is_rejected():
    with pytest.raises(ValidationError, match="both"):
        question(answer=None)


def test_passage_with_the_phrase_across_a_line_break_answers():
    text = "Customers may request a refund within\n30 days of purchase."

    assert answers(question(), passage("refunds.md", text))


def test_phrase_in_another_document_does_not_answer():
    assert not answers(question(), passage("billing.md", "within 30 days"))


def test_unanswerable_question_is_never_answered():
    assert not answers(question(None, None), passage("refunds.md", "within 30 days"))


def test_answer_rank_is_the_position_of_the_first_answer():
    passages = [passage("billing.md", "x"), passage("refunds.md", "within 30 days")]

    assert answer_rank(question(), passages) == 2
    assert answer_rank(question(), passages[:1]) == 0


def test_measure_counts_only_answerable_questions():
    knowledge = FakeKnowledge(
        [passage("billing.md", "x"), passage("refunds.md", "within 30 days")]
    )
    questions = [
        question(),  # answered at rank 2
        question("shipping.md", "flat fee"),  # not answered
        question(None, None),  # not counted
    ]

    assert measure(knowledge.search, questions) == SearchQuality(
        hit_at_1=0, hit_at_3=0.5, mean_reciprocal_rank=0.25
    )


def test_measure_without_answerable_questions_fails():
    with pytest.raises(ValueError, match="no answerable"):
        measure(FakeKnowledge().search, [question(None, None)])


def test_results_table_puts_the_best_setting_first():
    def result(size, mrr):
        quality = SearchQuality(0.5, 1.0, mrr)
        return ChunkSettingResult(size, 0, 9, vector=quality, keyword=quality)

    table = results_table([result(30, 0.4), result(120, 0.9)])

    lines = table.splitlines()
    assert lines[2].startswith("| 120 |")
    assert lines[3].startswith("| 30 |")


@pytest.mark.postgres
def test_each_chunk_setting_gets_its_own_index(knowledge_db):
    create_schema(knowledge_db)
    knowledge = KnowledgeBase(knowledge_db, KeywordEmbedder(), 60, 10)
    docs = {"refunds.md": "refund money back " * 10, "shipping.md": "shipping " * 10}
    questions = [
        EvalQuestion(id="Q-1", question="refund?", source="refunds.md", answer="back")
    ]

    results = compare_chunk_settings(knowledge, docs, questions, [(4, 0), (8, 2)])

    assert [(r.chunk_size, r.chunk_overlap) for r in results] == [(4, 0), (8, 2)]
    assert results[0].chunk_count > results[1].chunk_count
    assert all(r.vector.hit_at_3 == 1 for r in results)
    assert all(r.keyword.hit_at_3 == 1 for r in results)
    assert index_count(knowledge_db) == 2


def index_count(connection):
    return connection.execute("SELECT count(*) FROM knowledge_indexes").fetchone()[0]


def test_thresholds_count_kept_answers_and_questions_left_without_passages():
    def search(query, k):
        weak = passage("billing.md", "x").model_copy(update={"score": 0.55})
        if query == "answerable":
            return [weak, passage("refunds.md", "within 30 days")]  # answer at 0.8
        return [weak]

    questions = [
        EvalQuestion(id="Q-1", question="answerable", source="refunds.md", answer="30"),
        EvalQuestion(id="Q-2", question="other", source=None, answer=None),
    ]

    low, middle, high = compare_thresholds(search, questions, [0.5, 0.6, 0.9])

    assert (low.answer_kept, low.unanswerable_unsourced) == (1, 0)
    assert (middle.answer_kept, middle.unanswerable_unsourced) == (1, 1)
    assert (high.answer_kept, high.answerable_unsourced) == (0, 1)


def test_thresholds_need_both_kinds_of_questions():
    with pytest.raises(ValueError, match="answerable and unanswerable"):
        compare_thresholds(FakeKnowledge().search, [question()], [0.5])
