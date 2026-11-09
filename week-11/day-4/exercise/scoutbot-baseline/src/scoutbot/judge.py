"""Week 11 Day 3, Concept 3: an LLM-as-judge for the open-ended part of an eval.

Deterministic metrics (see `evals.py`) answer the questions a string comparison can: did the team route
to the right specialist, did a grounded answer actually cite a source. They are fast, free, and
unarguable. But they cannot answer *"is this a good reply?"* - is it on-topic, does it invent nothing,
would a customer be helped by it. That judgement is itself a language task, so the tool for it is another
model: an **LLM-as-judge**.

deepeval's `GEval` is that judge, wrapped in a metric. You give it a name, a few `evaluation_steps` (the
rubric), and which fields of the test case to look at; it prompts a model to score the output 0-10
against the rubric and returns that score normalised to 0-1. The one piece it needs is *a model to be
the judge*, and here is the whole trick that keeps this course's discipline intact:

**The judge is a swappable model, exactly like our patched `_client` seam.** deepeval lets you pass any
subclass of `DeepEvalBaseLLM` as the judge. So:

- `AnthropicJudge` wraps our own Anthropic SDK boundary (the same `_client()` seam as `core.triage`), so
  a real judged run costs a real - metered - model call, and you can point it at any tier (judging is a
  *batch, offline* cost, not a per-ticket one, so unlike Day 2 it can afford the strong tier by default).
- `StubJudge` returns a canned score with no network at all, so the eval harness, the GEval wiring, and
  every test run fully offline - the judge is faked the same way every other model call in this codebase
  is faked in a test.

Two spike findings baked in here so nobody re-discovers them the hard way:

- **Opt out of deepeval's phone-home *before* importing it** (the three env vars set at the top). Without
  them `import deepeval` tries to reach Confident AI. With them it is silent and offline. It still
  *prints* a "Run 'deepeval view'" nudge - that is a bare `print`, not a network call.
- **GEval scores on a 0-10 scale and divides by 10.** The judge fills a `{score: float, reason: str}`
  schema GEval hands it; return `score=9` to mean 0.9. The real judge asks the model for that number; the
  stub just returns it.
"""
import os

# deepeval phones home on import unless these are set first. Do it before the deepeval import below.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("ERROR_REPORTING", "NO")
os.environ.setdefault("DEEPEVAL_UPDATE_WARNING_OPT_OUT", "YES")

from typing import Optional

from anthropic import Anthropic
from deepeval.metrics import GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCaseParams
from pydantic import BaseModel

from .metering import TIERS, Meter, measure

# Judging is an offline, batch cost - you run it over a fixed eval set, not on every production ticket -
# so it can afford the strong tier by default, the opposite calculus from Day 2's per-ticket planner.
# Override with ANTHROPIC_JUDGE_MODEL.
JUDGE_MODEL = os.environ.get("ANTHROPIC_JUDGE_MODEL", TIERS["strong"])

# The rubric. Passing evaluation_steps explicitly is not just good practice - it makes GEval SKIP its own
# "generate the steps" model call, which is one fewer call to pay for and, crucially, the call that would
# otherwise reach the network before the judge model is even chosen. Keep the steps concrete and few.
ANSWER_QUALITY_STEPS = [
    "Read the customer ticket in 'input' and the support reply in 'actual output'.",
    "Reward a reply that directly addresses what the customer actually asked.",
    "Heavily penalise a reply that invents policy, amounts, or timeframes, or promises something the "
    "ticket gives no basis for.",
    "Reward an honest hand-off ('a teammate will follow up') over a confident guess when the answer is "
    "genuinely not known.",
    "Ignore tone and length; judge only whether the reply is correct, grounded, and useful.",
]


class JudgeError(RuntimeError):
    """Raised when the real judge model does not return a usable score. Loud beats a silent 0.0 - a
    judging call that quietly fails would report every answer as terrible, which reads as a real
    regression rather than the tooling fault it is."""


def _client() -> Anthropic:
    """The SDK boundary a test patches - identical seam to `core._client`/`planner._client`. Reads
    `ANTHROPIC_API_KEY` from the environment; nothing here hardcodes it."""
    return Anthropic()


class AnthropicJudge(DeepEvalBaseLLM):
    """A real LLM-as-judge: deepeval's judge interface over our own Anthropic SDK boundary.

    `generate(prompt, schema)` is what GEval calls. GEval hands it a rubric-filled prompt and a pydantic
    `schema` (a `{score: float, reason: str}` shape); this forces a single `submit_evaluation` tool call
    so the reply is always structured, then validates it back into that schema - the exact `tool_use` +
    `model_validate` pattern `core.triage` and `planner.plan_ticket` use. If a `meter` is passed, each
    judging call is recorded under the label `judge`, so the eval's own cost shows up in the run report.
    """

    def __init__(self, model: str = JUDGE_MODEL, meter: Optional[Meter] = None):
        self.model = model
        self.meter = meter

    def load_model(self):
        # deepeval calls this once; our client is created per-call in generate(), so nothing to build here.
        return self

    def get_model_name(self) -> str:
        return self.model

    def generate(self, prompt: str, schema: Optional[type] = None):
        """One judging call. With a `schema` (GEval's normal path) return a filled pydantic object; with
        none, return plain text. `max_tokens` is generous because the rubric asks for a reason too."""
        if schema is None:
            with measure() as sw:
                response = _client().messages.create(
                    model=self.model,
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
            if self.meter is not None:
                self.meter.record("judge", self.model, response.usage, sw.ms)
            parts = [b.text for b in response.content if getattr(b, "type", "") == "text"]
            return " ".join(parts).strip()

        tool = {
            "name": "submit_evaluation",
            "description": "Record the evaluation score and the reason for it.",
            "input_schema": schema.model_json_schema(),
        }
        with measure() as sw:
            response = _client().messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
                tools=[tool],
                tool_choice={"type": "tool", "name": "submit_evaluation"},
            )
        if self.meter is not None:
            self.meter.record("judge", self.model, response.usage, sw.ms)
        tool_uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
        if not tool_uses:
            raise JudgeError("Judge model did not call submit_evaluation.")
        return schema.model_validate(tool_uses[0].input)

    async def a_generate(self, prompt: str, schema: Optional[type] = None):
        # deepeval's batch evaluate() runs metrics on an event loop. The Anthropic sync client is fine to
        # call from here for a teaching-scale eval set; a production judge would use the async SDK client.
        return self.generate(prompt, schema)


class StubJudge(DeepEvalBaseLLM):
    """A deterministic, offline judge: returns a fixed score and reason, no network.

    This is to the judge what a patched `_client` is to `triage` - the seam that lets the eval harness and
    every test run with no key. `score` is on GEval's 0-10 scale (so `score=9` becomes a final 0.9). Pass
    a low score to prove a bad answer is caught; the default is a clear pass.
    """

    def __init__(self, score: float = 9.0, reason: str = "stub judge: canned score"):
        self._score = score
        self._reason = reason

    def load_model(self):
        return self

    def get_model_name(self) -> str:
        return "stub-judge"

    def generate(self, prompt: str, schema: Optional[type] = None):
        if schema is None:
            return self._reason
        return schema(score=self._score, reason=self._reason)

    async def a_generate(self, prompt: str, schema: Optional[type] = None):
        return self.generate(prompt, schema)


def answer_quality_metric(
    judge: Optional[DeepEvalBaseLLM] = None,
    *,
    threshold: float = 0.7,
) -> GEval:
    """The LLM-as-judge metric the eval escalates to for open-ended answer quality.

    A `GEval` scored by `judge` (defaults to a real `AnthropicJudge`; pass a `StubJudge` to run offline)
    against `ANSWER_QUALITY_STEPS`. It looks only at the ticket (`INPUT`) and the reply (`ACTUAL_OUTPUT`),
    scores 0-1, and passes at or above `threshold`. This is deliberately the *last* metric an eval runs:
    it is the only one that costs a model call, so the deterministic checks in `evals.py` go first and the
    judge earns its cost only on the question they cannot answer.
    """
    return GEval(
        name="Answer Quality",
        evaluation_steps=ANSWER_QUALITY_STEPS,
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=judge or AnthropicJudge(),
        threshold=threshold,
    )
