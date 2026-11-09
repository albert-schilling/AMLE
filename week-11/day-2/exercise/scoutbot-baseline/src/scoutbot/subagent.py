"""A subagent: an agent you call like a tool, that returns a result on a contract.

The other half of today. A hook guards a tool call; a **subagent** delegates a whole scoped task.
Instead of ScoutBot doing every step of a job itself - and cluttering its own transcript with the
retrieval, the reading, the second-guessing - it hands a bounded question to a smaller agent and gets
back one thing: a structured result. The parent never sees the subagent's internal steps. It depends
only on the shape of what comes back.

That shape is the **result contract**, and it is the point of the pattern. `ResearchResult` is a
Pydantic model - an answer, its sources, and a confidence score - and the subagent's output must
*validate* against it before the parent is allowed to see it. A subagent that rambles, or forgets its
sources, or returns free text, fails the contract loudly rather than quietly handing the parent
something it cannot rely on. Contrast a plain function call, where whatever the callee returns is what
you get: the contract is what makes delegation safe.

Two deliberate simplifications, both in the spirit of the rest of this codebase:

- **The synthesis step is injected.** A production research subagent would call a model to turn the
  retrieved passages into an answer. Here `ResearchSubagent` takes a `synthesize` callable, so the
  default (`passage_synthesize`) is a plain, offline, deterministic function over the passages, and a
  test can inject its own - including one that returns garbage, to prove the contract catches it. The
  teaching is the *contract and the delegation*, not a second LLM call.
- **The subagent is scoped to one job.** It retrieves against the policy knowledge base and answers a
  policy question. That narrowness is a feature: a subagent earns its keep by doing one bounded thing
  well and reporting back on a fixed shape, not by being a second general agent.

Exposed to the parent loop as one tool, `RESEARCH_TOOL` (`research_policy`), so from ScoutBot's side
delegating to the subagent looks exactly like calling any other tool - which is the whole ergonomic
idea: a subagent is a tool whose implementation happens to be another agent.
"""
from dataclasses import dataclass
from typing import Any, Callable, List

from pydantic import BaseModel, Field, ValidationError


class ResearchResult(BaseModel):
    """The contract a research subagent must satisfy before its answer reaches the parent.

    `confidence` is surfaced, not hidden, for the same reason the retriever surfaces its score: a
    confident-sounding answer with low confidence is exactly the signal the parent needs to decide
    whether to trust it or escalate. An answer with no sources is allowed by the type but discouraged
    by the prompt; an answer that is not a string, or a confidence outside a number, fails validation.
    """

    answer: str
    sources: List[str] = Field(default_factory=list)
    confidence: float


# A synthesis step turns the retrieved passages into something that must validate as a ResearchResult.
# Injected so the default can be offline and a test can supply its own (including an off-contract one).
Synthesize = Callable[[str, list], Any]


def passage_synthesize(question: str, hits: list) -> dict:
    """The default, offline synthesis: answer from the single best passage, cite them all.

    Deliberately deterministic and modelless - it stitches a result out of what retrieval returned,
    so the demo and tests run with no second API call. A real subagent would put a model here to
    actually *write* an answer from the passages; the shape it must return is unchanged, which is the
    point of the contract.
    """
    if not hits:
        return {"answer": "No relevant policy was found for that question.", "sources": [], "confidence": 0.0}
    top = hits[0]
    return {
        "answer": top.text,
        "sources": [h.source for h in hits],
        "confidence": round(float(top.score), 3),
    }


@dataclass
class ResearchSubagent:
    """A scoped agent that answers one policy question and returns a `ResearchResult`.

    `kb` is anything with a `.search(query, k=...)` method (the Week 9 `KnowledgeBase`, or a stub in
    tests). `synthesize` turns the retrieved passages into the result; it defaults to the offline
    `passage_synthesize`. `run` is the whole subagent: retrieve, synthesise, and enforce the contract
    before returning. If synthesis produces something off-contract, `run` returns a plain error dict
    the parent can react to - the failure is surfaced, never silently passed on.
    """

    kb: Any
    synthesize: Synthesize = passage_synthesize
    k: int = 3

    def run(self, question: str) -> dict:
        hits = self.kb.search(question, k=self.k)
        raw = self.synthesize(question, hits)
        try:
            result = ResearchResult.model_validate(raw)
        except ValidationError as exc:
            return {
                "error": "research subagent returned an off-contract result",
                "detail": exc.errors(include_url=False),
            }
        return result.model_dump()


RESEARCH_TOOL = {
    "name": "research_policy",
    "description": (
        "Delegate a focused policy question to a research subagent. It searches the support-policy "
        "knowledge base and returns a short answer with its sources and a confidence score between 0 "
        "and 1. Use it for a self-contained question you want answered before you draft a reply, "
        "rather than searching the policy yourself. Treat a low confidence score as a reason to "
        "hedge or escalate rather than to state the answer flatly."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The policy question to research."},
        },
        "required": ["question"],
    },
}
