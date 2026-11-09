"""Week 11 Day 3: eval-driven development - a dataset, deterministic metrics, and a harness.

Days 1-2 gave ScoutBot a team and a planner. The honest question this day asks is the one every prior
day dodged: **how do we know it is any good, and how would we know if a change made it worse?** "It
looked fine when I tried three tickets" is not an answer at production scale. An *eval* is: a fixed set
of cases, each with an expectation, run through metrics that score the system's output - so "is it
working?" becomes a number you can rerun on every change.

This module is the harness, built deepeval's way but kept transparent:

- `EvalCase` + `EVAL_SET` - the **dataset**. A handful of labelled tickets, each carrying what we expect
  (which specialist should handle it, whether a grounded answer must cite a source). The dataset is the
  asset; the code around it is replaceable.
- `build_test_cases` runs the team over the dataset and packages each run as a deepeval `LLMTestCase`
  (`input` the ticket, `actual_output` the answer, `retrieval_context` the passages, plus the routing
  facts in `metadata`). Collaborators are injected, so this runs offline with stubs.
- `RoutedCorrectlyMetric` and `CitesSourcesMetric` - **deterministic metrics** (deepeval `BaseMetric`
  subclasses) that touch no model. Did the ticket reach the right specialist? Did an answer that had to
  cite a source actually do it? These are fast, free, and unarguable, so **an eval leads with them** and
  only escalates to the LLM-as-judge (`judge.answer_quality_metric`) for the open-ended part.
- `run_suite` - a tiny, printable runner that scores every case against every metric. deepeval ships its
  own richer `evaluate()` (used in `run_evals.py`); `run_suite` is the same idea with nothing hidden, so
  a test can assert on the results directly.

Everything here runs with **no API key**: producing the outputs uses the deterministic orchestrator (no
model), and the deterministic metrics need no model either. Only the judge costs a call, which is why it
lives in its own module and its own demo.
"""
import os

# Match judge.py: opt out of deepeval's phone-home before it is imported (whichever module loads first).
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("ERROR_REPORTING", "NO")
os.environ.setdefault("DEEPEVAL_UPDATE_WARNING_OPT_OUT", "YES")

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from .knowledge import KnowledgeBase
from .orchestrator import (
    _default_order_lookup,
    build_orchestrator,
    initial_state,
)
from .tools import look_up_customer

# A bracketed source tag, e.g. "[refunds]" - the exact citation shape `knowledge.format_passages` emits
# and `core.GROUNDED_DRAFT_SYSTEM` asks the model to reproduce. The citation metric looks for one of these.
_CITATION_RE = re.compile(r"\[[a-z][a-z_]*\]")


@dataclass
class EvalCase:
    """One labelled ticket: the input, plus what a good run should do with it.

    `expected_route` is the specialist the dispatcher should pick; `must_cite` is True only for tickets a
    grounded (research) answer should back with a source. Deliberately small and declarative - the value
    of an eval is in the *cases*, so they read like a spec, not a script.
    """

    ticket_id: str
    ticket_text: str
    customer_id: str
    expected_route: str
    must_cite: bool = False
    refund_amount: float = 0.0


# The dataset. Small on purpose - big enough to cover every specialist and both a cite/no-cite answer,
# small enough to read at a glance. In real use this grows with every bug you find: a ticket that routed
# wrong becomes a permanent case, so the same mistake can never come back unnoticed.
EVAL_SET: List[EvalCase] = [
    EvalCase("E-1", "I was charged twice for my subscription and need a refund.", "1001", "refund", refund_amount=90.0),
    EvalCase("E-2", "Please refund the damaged item - I think I was overcharged too.", "1004", "refund", refund_amount=45.0),
    EvalCase("E-3", "Where is my order ORD-1042? It still hasn't arrived.", "1001", "order"),
    EvalCase("E-4", "My order ORD-2001 hasn't shipped yet, what's going on?", "1004", "order"),
    EvalCase("E-5", "How do I update the email address on my account?", "1002", "research", must_cite=True),
    EvalCase("E-6", "What is your policy on warranty claims for a defective product?", "1003", "research", must_cite=True),
]


def actual_route(state: dict) -> str:
    """Pull the specialist that actually handled the ticket out of the run transcript.

    The orchestrator logs `dispatch->refund`; this reads that back so the routing metric compares an
    *observed* route against the expected one, rather than trusting a field nobody checked.
    """
    for step in state.get("transcript", []):
        if step.startswith("dispatch->"):
            return step.split("->", 1)[1]
    return state.get("specialty") or ""


def to_test_case(case: EvalCase, state: dict) -> LLMTestCase:
    """Package one team run as a deepeval `LLMTestCase`.

    `input`/`actual_output` are what every metric reads; `retrieval_context` carries the passages the
    research worker found (so a faithfulness-style metric could use them); and `metadata` holds the
    routing facts and `must_cite` flag the deterministic metrics need. One function so the shape a test
    asserts on is the shape the metrics receive.
    """
    passages = (state.get("finding") or {}).get("passages") or []
    return LLMTestCase(
        input=case.ticket_text,
        actual_output=state.get("answer", ""),
        retrieval_context=[f"[{p['source']}] {p['text']}" for p in passages] or None,
        metadata={
            "ticket_id": case.ticket_id,
            "expected_route": case.expected_route,
            "actual_route": actual_route(state),
            "must_cite": case.must_cite,
        },
    )


def build_test_cases(
    cases: List[EvalCase] = EVAL_SET,
    *,
    get_customer: Callable[[str], dict] = look_up_customer,
    get_order_status: Callable[[str], dict] = _default_order_lookup,
    kb: Optional[KnowledgeBase] = None,
) -> List[LLMTestCase]:
    """Run the team over the dataset and return one `LLMTestCase` per case.

    Uses `build_orchestrator`, whose dispatcher is a deterministic keyword rule and whose workers reuse
    the rules table, an order lookup, and retrieval - so producing the outputs needs **no model call**.
    Every collaborator is injected, so a test passes stubs and the whole thing runs with no files and no
    network; the demo passes the real ones.
    """
    team = build_orchestrator(get_customer=get_customer, get_order_status=get_order_status, kb=kb)
    out = []
    for case in cases:
        state = team.invoke(
            initial_state(case.ticket_id, case.ticket_text, case.customer_id, case.refund_amount)
        )
        out.append(to_test_case(case, state))
    return out


class RoutedCorrectlyMetric(BaseMetric):
    """Deterministic metric: did the ticket reach the specialist it should have?

    A `BaseMetric` that never calls a model - it compares the observed route against the expected one,
    both carried in `metadata`. This is the kind of check an eval leads with: a routing regression (the
    planner sends refunds to the research worker) is caught here, instantly and for free, without asking a
    judge whether the answer "seemed fine".
    """

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        meta = test_case.metadata or {}
        expected, actual = meta.get("expected_route"), meta.get("actual_route")
        self.score = 1.0 if actual == expected else 0.0
        self.success = self.score >= self.threshold
        self.reason = f"expected route {expected!r}, got {actual!r}"
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(getattr(self, "success", False))

    @property
    def __name__(self):
        return "Routed Correctly"


class CitesSourcesMetric(BaseMetric):
    """Deterministic metric: does an answer that had to cite a source actually cite one?

    For a case flagged `must_cite`, the answer has to contain a bracketed source tag (`[refunds]`); a
    grounded reply that forgot to cite fails here. For a case that need not cite (a refund or order
    answer), this passes trivially - the metric only asserts what the case asked for. Again, no model:
    citation is a property of the text, so a regex settles it.
    """

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        meta = test_case.metadata or {}
        if not meta.get("must_cite"):
            self.score = 1.0
            self.success = True
            self.reason = "citation not required for this ticket"
            return self.score
        cited = bool(_CITATION_RE.search(test_case.actual_output or ""))
        self.score = 1.0 if cited else 0.0
        self.success = self.score >= self.threshold
        self.reason = "found a [source] citation" if cited else "grounded answer cited no source"
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(getattr(self, "success", False))

    @property
    def __name__(self):
        return "Cites Sources"


@dataclass
class CaseScore:
    """One metric's verdict on one case - the flat, printable row `run_suite` collects."""

    ticket_id: str
    metric: str
    score: float
    success: bool
    reason: str


@dataclass
class SuiteResult:
    """The result of running a suite: every `CaseScore`, plus the roll-ups a gate would check."""

    scores: List[CaseScore] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.scores if s.success)

    @property
    def total(self) -> int:
        return len(self.scores)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def failures(self) -> List[CaseScore]:
        return [s for s in self.scores if not s.success]

    def report(self) -> str:
        lines = [f"{'ticket':<8} {'metric':<18} {'score':>6} {'ok':>4}  reason"]
        for s in self.scores:
            lines.append(
                f"{s.ticket_id:<8} {s.metric:<18} {s.score:>6.2f} {('yes' if s.success else 'NO'):>4}  {s.reason}"
            )
        lines.append(f"\n{self.passed}/{self.total} checks passed ({self.pass_rate:.0%})")
        return "\n".join(lines)


def run_suite(test_cases: List[LLMTestCase], metrics: List[BaseMetric]) -> SuiteResult:
    """Score every case against every metric - a transparent stand-in for deepeval's `evaluate()`.

    The whole of an eval harness in one loop: for each case, run each metric and collect its score,
    pass/fail, and reason. Returns a `SuiteResult` a test can assert on or a script can print. deepeval's
    own `evaluate()` (see `run_evals.py`) does the same with a richer report and parallelism; this exists
    so the mechanism is not a black box - an eval is just metrics run over cases.
    """
    result = SuiteResult()
    for tc in test_cases:
        ticket_id = (tc.metadata or {}).get("ticket_id", "?")
        for metric in metrics:
            metric.measure(tc)
            result.scores.append(
                CaseScore(
                    ticket_id=ticket_id,
                    metric=metric.__name__,
                    score=float(metric.score),
                    success=metric.is_successful(),
                    reason=metric.reason,
                )
            )
    return result
