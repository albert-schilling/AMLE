"""The retrieval node, alone and in the real graph; model and knowledge base faked."""

import pytest
from helpers import REFUND_PASSAGE, retrieval, runtime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime

from ticket_classifier.checkpoint import thread_config
from ticket_classifier.context import MissingContextError
from ticket_classifier.graph import build_workflow
from ticket_classifier.models import Search
from ticket_classifier.nodes.retrieve_knowledge import (
    MissingQueryError,
    node_retrieve_knowledge,
)
from ticket_classifier.runner import run_ticket

REFUND_SEARCH = Search(queries=("so angry", "refund"))


def test_searches_the_latest_query_with_top_k(knowledge, make_ticket, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_TOP_K", "2")
    state = {"ticket": make_ticket(text="I am so angry!"), "search": REFUND_SEARCH}

    update = node_retrieve_knowledge(state, runtime(knowledge))

    assert update == {"search": REFUND_SEARCH.with_result(retrieval(REFUND_PASSAGE))}
    assert knowledge.queries == [("refund", 2)]


def test_splits_off_passages_below_the_minimum_score(
    knowledge, make_ticket, monkeypatch
):
    monkeypatch.setenv("KNOWLEDGE_MIN_SCORE", "0.6")
    weak = REFUND_PASSAGE.model_copy(update={"ordinal": 2, "score": 0.59})
    edge = REFUND_PASSAGE.model_copy(update={"ordinal": 3, "score": 0.6})
    knowledge.passages = [REFUND_PASSAGE, edge, weak]
    state = {"ticket": make_ticket(), "search": REFUND_SEARCH}

    update = node_retrieve_knowledge(state, runtime(knowledge))

    assert update["search"].result == retrieval(REFUND_PASSAGE, edge, weak=[weak])


def test_without_query_names_the_problem(knowledge, make_ticket):
    with pytest.raises(MissingQueryError):
        node_retrieve_knowledge(
            {"ticket": make_ticket(), "search": Search()}, runtime(knowledge)
        )


def test_without_context_names_the_problem(make_ticket):
    with pytest.raises(MissingContextError):
        node_retrieve_knowledge(
            {"ticket": make_ticket(), "search": REFUND_SEARCH}, Runtime(context=None)
        )


def test_passages_are_saved_with_the_run(model, workflow_context, make_ticket):
    workflow = build_workflow(InMemorySaver())

    run_ticket(workflow, workflow_context, make_ticket(id="T-1"))

    saved = workflow.get_state(thread_config("T-1")).values
    assert saved["search"].result == retrieval(REFUND_PASSAGE)
