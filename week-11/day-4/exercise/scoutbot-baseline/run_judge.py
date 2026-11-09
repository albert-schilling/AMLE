"""Week 11 Day 3 demo: the real LLM-as-judge grading answer quality - this one NEEDS an API key.

The deterministic metrics (run_evals.py) settle everything a string can. This demo shows the part they
cannot: *is this actually a good reply?* It runs the same GEval "Answer Quality" metric, but backed by a
real `AnthropicJudge` instead of the stub, over two hand-written replies to the same ticket - one honest
and grounded, one confidently wrong - and prints the judge's score and its reason for each.

Two teaching points are built in:

- The judge catches what a regex cannot: the confident-wrong answer invents a refund window, and only a
  judge that reads for meaning scores it down. That is the whole case for an LLM-as-judge.
- Judging costs a real model call, so it is metered. Note it is a *batch, offline* cost - you pay it over
  a fixed eval set, not on every production ticket - which is why the judge defaults to the strong tier
  (the opposite calculus from Day 2's per-ticket planner). Override with ANTHROPIC_JUDGE_MODEL.

Requires ANTHROPIC_API_KEY (put it in .env). Without a key, run run_evals.py, which is fully offline.
"""
import os
import sys

from dotenv import load_dotenv
from deepeval.test_case import LLMTestCase

from scoutbot.judge import AnthropicJudge, JUDGE_MODEL, answer_quality_metric
from scoutbot.metering import Meter

TICKET = "How long do refunds take to process once approved?"

# The kind of grounded, honest reply the research worker produces.
GOOD_ANSWER = (
    "Based on our policy, approved refunds are issued within five business days [refunds]. "
    "You'll get an email confirmation once it's processed."
)
# A confidently wrong reply: invents a number no passage supports. A regex sees a fine, fluent sentence;
# only a judge that reads for meaning catches that it made the timeframe up.
BAD_ANSWER = "Refunds are instant and always credited back to your card within 30 minutes, guaranteed."


def main() -> None:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("This demo needs ANTHROPIC_API_KEY (the judge is a real model call).")
        print("Put it in .env, or run run_evals.py for the fully offline version.")
        sys.exit(1)

    meter = Meter()
    judge = AnthropicJudge(model=JUDGE_MODEL, meter=meter)
    metric = answer_quality_metric(judge, threshold=0.7)

    print(f"Judging two replies to the same ticket with a real LLM-as-judge ({JUDGE_MODEL}):\n")
    print(f"Ticket: {TICKET}\n")
    for label, answer in (("grounded/honest", GOOD_ANSWER), ("confidently wrong", BAD_ANSWER)):
        tc = LLMTestCase(input=TICKET, actual_output=answer)
        metric.measure(tc)
        verdict = "PASS" if metric.is_successful() else "FAIL"
        print("-" * 84)
        print(f"[{label}] {answer}")
        print(f"  score  : {metric.score:.2f}  -> {verdict} (threshold {metric.threshold})")
        print(f"  reason : {metric.reason}")

    print("-" * 84)
    print("\nWhat the judge cost (batch/offline - paid over the eval set, not per production ticket):")
    print(meter.report())


if __name__ == "__main__":
    main()
