"""The retrieval node, alone and in the real graph; model and knowledge base faked."""

import pytest
from helpers import REFUND_PASSAGE, retrieval
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime

from ticket_classifier.checkpoint import thread_config
from ticket_classifier.context import WorkflowContext
from ticket_classifier.graph import build_workflow
from ticket_classifier.models import RetrievalResult
from ticket_classifier.nodes import MissingContextError, node_retrieve_knowledge
from ticket_classifier.runner import run_ticket


def test_searches_with_the_ticket_text_and_top_k(knowledge, make_ticket, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_TOP_K", "2")
    state = {"ticket": make_ticket(text="Where is my refund?")}

    update = node_retrieve_knowledge(
        state, Runtime(context=WorkflowContext(knowledge=knowledge))
    )

    assert update == {"retrieval": retrieval(REFUND_PASSAGE)}
    assert knowledge.queries == [("Where is my refund?", 2)]


def test_leaves_out_passages_below_the_minimum_score(
    knowledge, make_ticket, monkeypatch
):
    monkeypatch.setenv("KNOWLEDGE_MIN_SCORE", "0.6")
    weak = REFUND_PASSAGE.model_copy(update={"ordinal": 2, "score": 0.59})
    edge = REFUND_PASSAGE.model_copy(update={"ordinal": 3, "score": 0.6})
    knowledge.passages = [REFUND_PASSAGE, edge, weak]

    update = node_retrieve_knowledge(
        {"ticket": make_ticket()}, Runtime(context=WorkflowContext(knowledge=knowledge))
    )

    assert update == {
        "retrieval": RetrievalResult(
            passages=[REFUND_PASSAGE, edge], min_score=0.6, dropped=1
        )
    }


def test_without_context_names_the_problem(make_ticket):
    with pytest.raises(MissingContextError):
        node_retrieve_knowledge({"ticket": make_ticket()}, Runtime(context=None))


def test_passages_are_saved_with_the_run(model, workflow_context, make_ticket):
    workflow = build_workflow(InMemorySaver())

    run_ticket(workflow, workflow_context, make_ticket(id="T-1"))

    saved = workflow.get_state(thread_config("T-1")).values
    assert saved["retrieval"] == retrieval(REFUND_PASSAGE)


def test_retrieval_runs_after_the_customer_and_before_triage():
    edges = {(e.source, e.target) for e in build_workflow().get_graph().edges}

    assert ("get_customer", "retrieve_knowledge") in edges
    assert ("retrieve_knowledge", "triage") in edges
    assert ("get_customer", "triage") not in edges
