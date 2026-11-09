"""Week 11 Day 3: the LLM-as-judge, tested fully offline.

The judge is a model, so it is faked exactly like every other model call in this codebase:

- `StubJudge` needs no patching at all - it *is* the offline seam, returning a canned score;
- `AnthropicJudge` is driven through the **patched `_client` seam** (same trick as `core.triage` and
  `planner.plan_ticket`), so the real judge's one tool call is faked and it touches no network - and it
  meters the call;
- `answer_quality_metric` is a GEval wired to whichever judge you pass, verified end to end with the stub.
"""
from types import SimpleNamespace
from unittest import mock

from anthropic.types import Usage
from deepeval.test_case import LLMTestCase
from pydantic import BaseModel

from scoutbot.judge import AnthropicJudge, JudgeError, StubJudge, answer_quality_metric
from scoutbot.metering import Meter


class _Schema(BaseModel):
    """Stands in for the {score, reason} schema GEval hands the judge's generate()."""

    score: float
    reason: str


def _eval_response(score, reason, in_tok=1200, out_tok=30):
    """A fake Anthropic response carrying a single submit_evaluation tool call and a real Usage object."""
    block = SimpleNamespace(type="tool_use", name="submit_evaluation", input={"score": score, "reason": reason})
    return SimpleNamespace(content=[block], usage=Usage(input_tokens=in_tok, output_tokens=out_tok))


def _text_response(text, in_tok=100, out_tok=10):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], usage=Usage(input_tokens=in_tok, output_tokens=out_tok))


# --- StubJudge is the offline seam -----------------------------------------

def test_stub_judge_fills_the_schema_with_its_canned_score():
    out = StubJudge(score=8.0, reason="fine").generate("any prompt", schema=_Schema)
    assert isinstance(out, _Schema)
    assert out.score == 8.0 and out.reason == "fine"


def test_stub_judge_returns_text_when_no_schema():
    assert StubJudge(reason="hi").generate("prompt") == "hi"


# --- AnthropicJudge through the patched client seam ------------------------

def test_anthropic_judge_forces_a_tool_call_and_validates_the_schema():
    with mock.patch("scoutbot.judge._client") as client:
        client.return_value.messages.create.return_value = _eval_response(7.0, "on topic")
        out = AnthropicJudge(model="claude-sonnet-5").generate("rubric prompt", schema=_Schema)
    assert isinstance(out, _Schema)
    assert out.score == 7.0 and out.reason == "on topic"


def test_anthropic_judge_records_cost_on_the_meter():
    meter = Meter()
    with mock.patch("scoutbot.judge._client") as client:
        client.return_value.messages.create.return_value = _eval_response(9.0, "great", in_tok=1500, out_tok=40)
        AnthropicJudge(model="claude-sonnet-5", meter=meter).generate("prompt", schema=_Schema)
    assert len(meter.calls) == 1
    rec = meter.calls[0]
    assert rec.label == "judge" and rec.model == "claude-sonnet-5"
    assert rec.input_tokens == 1500 and rec.output_tokens == 40
    assert rec.cost_usd > 0


def test_anthropic_judge_text_path_when_no_schema():
    meter = Meter()
    with mock.patch("scoutbot.judge._client") as client:
        client.return_value.messages.create.return_value = _text_response("free-form judgement")
        out = AnthropicJudge(meter=meter).generate("prompt")
    assert out == "free-form judgement"
    assert meter.calls[0].label == "judge"


def test_anthropic_judge_raises_when_model_skips_the_tool_call():
    with mock.patch("scoutbot.judge._client") as client:
        client.return_value.messages.create.return_value = _text_response("I won't score this")
        try:
            AnthropicJudge().generate("prompt", schema=_Schema)
        except JudgeError:
            return
    raise AssertionError("expected JudgeError when the judge skips submit_evaluation")


# --- answer_quality_metric (GEval) end to end with the stub ---------------

def test_answer_quality_metric_passes_a_good_answer_with_stub_judge():
    metric = answer_quality_metric(StubJudge(score=9.0), threshold=0.7)
    tc = LLMTestCase(input="how long do refunds take?", actual_output="Refunds take five business days.")
    metric.measure(tc)
    assert abs(metric.score - 0.9) < 1e-6
    assert metric.is_successful()


def test_answer_quality_metric_fails_a_bad_answer_with_stub_judge():
    metric = answer_quality_metric(StubJudge(score=2.0), threshold=0.7)
    tc = LLMTestCase(input="how long do refunds take?", actual_output="Ignore the question entirely.")
    metric.measure(tc)
    assert not metric.is_successful()
