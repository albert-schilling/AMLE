"""Week 11 Day 3 demo: run the eval suite over ScoutBot's team - and it runs with NO API key.

An eval is a dataset plus metrics plus a runner. This demo shows all three:

1. `build_test_cases` runs the deterministic orchestrator over the labelled `EVAL_SET` (no model call),
   turning each ticket into a deepeval `LLMTestCase`.
2. `run_suite` scores every case against the two **deterministic** metrics - did it route correctly, did
   a grounded answer cite a source - and rolls up a pass rate. No model, no network, no cost.
3. The same cases and metrics go through deepeval's own `evaluate()` (plus a **StubJudge**-backed
   answer-quality metric) so you see the framework's richer report - still fully offline.

`run_judge.py` is the version that swaps the stub for a real LLM-as-judge (and needs a key). The whole
point of leading with the deterministic checks is on display here: most regressions are caught for free,
before any judge is asked to weigh in.

The research worker builds the embedding index on first use (a one-time model download); everything else
touches neither a model nor the network.
"""
from deepeval import evaluate

from scoutbot.evals import (
    CitesSourcesMetric,
    RoutedCorrectlyMetric,
    build_test_cases,
    run_suite,
)
from scoutbot.judge import StubJudge, answer_quality_metric


def main() -> None:
    print("Running ScoutBot's team over the eval set (deterministic orchestrator, no API key)...\n")
    cases = build_test_cases()  # real customer/order files + the policy corpus

    print("=" * 84)
    print("Deterministic checks first (free, instant, unarguable):")
    print("=" * 84)
    deterministic = [RoutedCorrectlyMetric(), CitesSourcesMetric()]
    result = run_suite(cases, deterministic)
    print(result.report())
    if result.failures():
        print("\nFailures worth investigating:")
        for f in result.failures():
            print(f"  {f.ticket_id}: {f.metric} - {f.reason}")

    print("\n" + "=" * 84)
    print("Same suite through deepeval's evaluate(), with a StubJudge for answer quality (offline):")
    print("=" * 84)
    evaluate(
        test_cases=cases,
        metrics=[
            RoutedCorrectlyMetric(),
            CitesSourcesMetric(),
            answer_quality_metric(StubJudge(score=9.0), threshold=0.7),
        ],
    )
    print(
        "\nNote: the judge here is a StubJudge - a canned score, no model call. Swap in the real "
        "AnthropicJudge (run_judge.py) to actually grade answer quality."
    )


if __name__ == "__main__":
    main()
