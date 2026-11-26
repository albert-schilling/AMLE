"""The retrieval loop: write a query, search, judge, reword. Model, knowledge faked."""

from graphlib import TopologicalSorter

import anthropic
import httpx
import pytest
from helpers import REFUND_PASSAGE, WEAK_PASSAGE, ScriptedQueries, retrieved, runtime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime

from ticket_classifier.checkpoint import thread_config
from ticket_classifier.context import MissingContextError, WorkflowContext
from ticket_classifier.graph import build_workflow
from ticket_classifier.models import Retrieval
from ticket_classifier.nodes import (
    node_critique_retrieval,
    node_formulate_query,
    route_after_critique,
)
from ticket_classifier.nodes.critique_retrieval import MissingResultError
from ticket_classifier.runner import run_ticket


def test_first_query_starts_the_search(knowledge, make_ticket):
    write_query = ScriptedQueries("refund double charge")
    state = {"ticket": make_ticket(), "retrieval": Retrieval()}

    update = node_formulate_query(state, runtime(knowledge, write_query))

    assert update == {"retrieval": Retrieval(queries=("refund double charge",))}
    assert write_query.calls == [Retrieval()]


def test_reword_gets_the_failed_search(knowledge, make_ticket):
    write_query = ScriptedQueries("billing duplicate payment")
    failed = retrieved(weak=[WEAK_PASSAGE], queries=["charged twice"]).judged(False)
    state = {"ticket": make_ticket(), "retrieval": failed}

    update = node_formulate_query(state, runtime(knowledge, write_query))

    assert write_query.calls == [failed]  # with its queries and weak passages
    assert update["retrieval"] == Retrieval(
        queries=("charged twice", "billing duplicate payment")
    )


def test_formulate_query_without_context_names_the_problem(make_ticket):
    with pytest.raises(MissingContextError):
        node_formulate_query(
            {"ticket": make_ticket(), "retrieval": Retrieval()}, Runtime(context=None)
        )


@pytest.mark.parametrize(
    ("retrieval", "ok"),
    [(retrieved(REFUND_PASSAGE), True), (retrieved(weak=[WEAK_PASSAGE]), False)],
)
def test_critique_passes_a_passage_above_the_minimum_score(make_ticket, retrieval, ok):
    update = node_critique_retrieval({"ticket": make_ticket(), "retrieval": retrieval})

    assert update == {"retrieval": retrieval.judged(ok)}


def test_critique_without_result_names_the_problem(make_ticket):
    with pytest.raises(MissingResultError):
        node_critique_retrieval({"ticket": make_ticket(), "retrieval": Retrieval()})


@pytest.mark.parametrize(
    ("ok", "attempts", "route"),
    [
        (True, 1, "retrieval_done"),
        (False, 1, "reformulate"),
        (False, 3, "retrieval_done"),  # attempts spent: go on without sources
    ],
)
def test_route_after_critique(ok, attempts, route):
    retrieval = retrieved(queries=["query"] * attempts).judged(ok)

    assert route_after_critique({"retrieval": retrieval}) == route


def test_route_after_critique_follows_the_setting(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_MAX_ATTEMPTS", "1")
    retrieval = retrieved(queries=["query"]).judged(False)

    assert route_after_critique({"retrieval": retrieval}) == "retrieval_done"


@pytest.fixture
def run_with(model, knowledge, make_ticket):
    """Run one ticket with scripted queries; returns its saved state."""

    def run(write_query):
        workflow = build_workflow(InMemorySaver())
        context = WorkflowContext(knowledge=knowledge, write_query=write_query)
        run_ticket(workflow, context, make_ticket(id="T-1"))
        return workflow.get_state(thread_config("T-1")).values

    return run


def test_weak_then_strong_search_rewords_once(run_with, knowledge, model):
    knowledge.passages = [WEAK_PASSAGE]
    knowledge.by_query = {"refund": [REFUND_PASSAGE]}

    saved = run_with(ScriptedQueries("so angry", "refund"))

    assert saved["retrieval"].queries == ("so angry", "refund")
    assert saved["retrieval"].ok is True
    triage_prompt = model.call_args.kwargs["messages"][0]["content"]
    assert REFUND_PASSAGE.text in triage_prompt  # from the second search


def test_always_weak_search_stops_at_the_bound(run_with, knowledge, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_MAX_ATTEMPTS", "3")
    knowledge.passages = [WEAK_PASSAGE]

    saved = run_with(ScriptedQueries("gift card", "voucher", "present card"))

    assert saved["retrieval"].queries == ("gift card", "voucher", "present card")
    assert saved["retrieval"].ok is False
    assert not saved["reply"].has_sources
    assert len(knowledge.queries) == 3


def test_the_only_cycle_is_critique_back_to_formulate_query():
    graph = build_workflow().get_graph()
    edges = {(e.source, e.target): e for e in graph.edges}
    back = ("critique_retrieval", "formulate_query")

    assert edges[back].data == "reformulate"
    assert ("critique_retrieval", "triage") in edges
    # Without the back-edge the graph has no cycle left.
    sorter = TopologicalSorter()
    for source, target in edges.keys() - {back}:
        sorter.add(target, source)
    sorter.prepare()  # raises CycleError on a cycle


def test_failed_query_call_continues_in_the_loop_on_the_next_run(
    knowledge, model, make_ticket
):
    knowledge.passages = [WEAK_PASSAGE]
    knowledge.by_query = {"refund": [REFUND_PASSAGE]}
    timeout = anthropic.APITimeoutError(httpx.Request("POST", "https://api.test"))
    write_query = ScriptedQueries("so angry", timeout, "refund")
    context = WorkflowContext(knowledge=knowledge, write_query=write_query)
    workflow = build_workflow(InMemorySaver())
    ticket = make_ticket(id="T-1")

    with pytest.raises(anthropic.APITimeoutError):
        run_ticket(workflow, context, ticket)
    assert workflow.get_state(thread_config("T-1")).next == ("formulate_query",)

    run_ticket(workflow, context, ticket)

    saved = workflow.get_state(thread_config("T-1")).values
    assert saved["retrieval"].queries == ("so angry", "refund")
    assert saved["retrieval"].ok is True
