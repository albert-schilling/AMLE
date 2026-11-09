"""Week 11 Day 3: the eval harness and its deterministic metrics, tested fully offline.

Four kinds of test, mirroring the day:

- the **deterministic metrics** are pure functions over a hand-made `LLMTestCase` - no team, no model;
- `actual_route` reads the route back out of a transcript;
- `build_test_cases` runs the **whole team over the dataset with injected stubs**, so producing the eval
  inputs needs no files, no key, no network; and
- `run_suite` scores those cases and rolls up a pass rate, including one case run through the **StubJudge**
  so the GEval path is exercised offline too.
"""
from types import SimpleNamespace

from deepeval.test_case import LLMTestCase

from scoutbot.evals import (
    EVAL_SET,
    CitesSourcesMetric,
    RoutedCorrectlyMetric,
    actual_route,
    build_test_cases,
    run_suite,
    to_test_case,
)
from scoutbot.judge import StubJudge, answer_quality_metric


# --- fakes (same shapes as test_orchestrator / test_planner) ---------------

def _hit(source, text):
    return SimpleNamespace(source=source, ordinal=0, text=text, score=0.9)


class StubKB:
    def __init__(self, hits):
        self._hits = hits

    def search(self, query, *, k=3):
        return self._hits[:k]


CUSTOMERS = {
    "1001": {"found": True, "customer_id": "1001", "plan": "pro", "past_refunds_90d": 2},
    "1002": {"found": True, "customer_id": "1002", "plan": "free", "past_refunds_90d": 0},
    "1003": {"found": True, "customer_id": "1003", "plan": "pro", "past_refunds_90d": 0},
    "1004": {"found": True, "customer_id": "1004", "plan": "free", "past_refunds_90d": 4},
}


def _get_customer(cid):
    return CUSTOMERS.get(cid, {"found": False, "customer_id": cid})


def _get_order(order_id):
    return {"found": True, "order_id": order_id.upper(), "status": "in_transit", "carrier": "DHL"}


HITS = [_hit("refunds", "Refunds are issued within five business days.")]


def _case(expected_route, actual_route, *, output="", must_cite=False):
    return LLMTestCase(
        input="a ticket",
        actual_output=output,
        metadata={
            "ticket_id": "T",
            "expected_route": expected_route,
            "actual_route": actual_route,
            "must_cite": must_cite,
        },
    )


# --- deterministic metrics are pure functions over a test case -------------

def test_routed_correctly_passes_when_routes_match():
    m = RoutedCorrectlyMetric()
    assert m.measure(_case("refund", "refund")) == 1.0
    assert m.is_successful()


def test_routed_correctly_fails_when_routes_differ():
    m = RoutedCorrectlyMetric()
    assert m.measure(_case("order", "refund")) == 0.0
    assert not m.is_successful()
    assert "order" in m.reason and "refund" in m.reason


def test_cites_sources_requires_a_bracketed_source_when_must_cite():
    m = CitesSourcesMetric()
    assert m.measure(_case("research", "research", output="Based on our policy:\n[refunds] ...", must_cite=True)) == 1.0
    assert m.is_successful()


def test_cites_sources_fails_a_grounded_answer_with_no_citation():
    m = CitesSourcesMetric()
    assert m.measure(_case("research", "research", output="Refunds take five days.", must_cite=True)) == 0.0
    assert not m.is_successful()


def test_cites_sources_passes_trivially_when_citation_not_required():
    m = CitesSourcesMetric()
    # a refund answer need not cite - the metric only asserts what the case asked for
    assert m.measure(_case("refund", "refund", output="A refund of EUR 20 is approved.", must_cite=False)) == 1.0
    assert m.is_successful()


# --- actual_route reads the route out of a transcript ----------------------

def test_actual_route_reads_dispatch_step_from_transcript():
    state = {"transcript": ["look_up_customer", "dispatch->order", "finalize"], "specialty": "order"}
    assert actual_route(state) == "order"


def test_actual_route_falls_back_to_specialty_without_a_dispatch_step():
    assert actual_route({"transcript": ["look_up_customer"], "specialty": "research"}) == "research"


# --- build_test_cases runs the whole team over the dataset, offline --------

def _built():
    return build_test_cases(
        get_customer=_get_customer,
        get_order_status=_get_order,
        kb=StubKB(HITS),
    )


def test_build_test_cases_produces_one_case_per_eval_case_with_answers():
    cases = _built()
    assert len(cases) == len(EVAL_SET)
    for tc in cases:
        assert tc.actual_output  # every run produced a customer-facing answer
        assert tc.metadata["actual_route"]  # and was routed somewhere


def test_build_test_cases_routes_every_dataset_case_to_its_expected_specialist():
    # the dataset is written so the deterministic dispatcher gets all of them right - a routing
    # regression later would turn one of these red, which is the whole point of keeping the eval
    cases = _built()
    result = run_suite(cases, [RoutedCorrectlyMetric()])
    assert result.pass_rate == 1.0, result.report()


def test_research_cases_carry_retrieval_context_and_cite_sources():
    cases = _built()
    result = run_suite(cases, [CitesSourcesMetric()])
    assert result.pass_rate == 1.0, result.report()
    research = [tc for tc in cases if tc.metadata["must_cite"]]
    assert research and all(tc.retrieval_context for tc in research)


# --- run_suite rolls up a pass rate, and the judge path runs offline -------

def test_run_suite_rolls_up_pass_rate_and_lists_failures():
    good = _case("refund", "refund")
    bad = _case("order", "refund")
    result = run_suite([good, bad], [RoutedCorrectlyMetric()])
    assert result.total == 2 and result.passed == 1
    assert result.pass_rate == 0.5
    assert [s.ticket_id for s in result.failures()] == ["T"]


def test_run_suite_scores_answer_quality_with_a_stub_judge_offline():
    cases = _built()
    metric = answer_quality_metric(StubJudge(score=9.0), threshold=0.7)
    result = run_suite(cases, [metric])
    # the stub judge passes every answer at 0.9; this proves the GEval path runs with no key
    assert result.pass_rate == 1.0, result.report()
    assert all(abs(s.score - 0.9) < 1e-6 for s in result.scores)


def test_stub_judge_can_fail_a_bad_answer():
    metric = answer_quality_metric(StubJudge(score=2.0), threshold=0.7)
    result = run_suite([_case("refund", "refund", output="garbage")], [metric])
    assert result.passed == 0
