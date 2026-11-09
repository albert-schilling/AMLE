"""Week 10 Day 3: the research subagent and its result contract, tested offline.

No API key and no network. The subagent's retrieval runs against a tiny stub knowledge base (a fixed
list of hits, no embedder), and its synthesis step is injected, so every path - a good result, an
off-contract result, an empty corpus - is checkable with plain objects.
"""
from types import SimpleNamespace
from unittest.mock import patch

from scoutbot.subagent import RESEARCH_TOOL, ResearchResult, ResearchSubagent, passage_synthesize
from scoutbot.loop import run_agent_loop


def _hit(source, text, score):
    return SimpleNamespace(source=source, text=text, score=score)


class StubKB:
    def __init__(self, hits):
        self._hits = hits

    def search(self, query, *, k=3):
        return self._hits[:k]


HITS = [
    _hit("refunds", "Refunds are issued within five business days.", 0.88),
    _hit("refunds", "Refunds go back to the original payment method.", 0.71),
]


# ---------------------------------------------------------------------------
# The default offline synthesis
# ---------------------------------------------------------------------------

def test_passage_synthesize_builds_a_result_from_the_top_passage():
    out = passage_synthesize("how long do refunds take?", HITS)
    assert out["answer"] == "Refunds are issued within five business days."
    assert out["sources"] == ["refunds", "refunds"]
    assert out["confidence"] == 0.88


def test_passage_synthesize_handles_an_empty_corpus():
    out = passage_synthesize("anything", [])
    assert out["confidence"] == 0.0
    assert out["sources"] == []


# ---------------------------------------------------------------------------
# The subagent and its contract
# ---------------------------------------------------------------------------

def test_subagent_returns_a_validated_result_dict():
    agent = ResearchSubagent(kb=StubKB(HITS))
    out = agent.run("how long do refunds take?")
    # Round-trips through the ResearchResult contract, so the shape is guaranteed.
    result = ResearchResult.model_validate(out)
    assert result.answer.startswith("Refunds are issued")
    assert result.confidence == 0.88


def test_an_off_contract_synthesis_is_caught_not_passed_on():
    # A synthesize that forgets the required `answer`/`confidence` fields must not reach the parent.
    def broken(question, hits):
        return {"sources": ["refunds"]}  # missing answer and confidence

    out = ResearchSubagent(kb=StubKB(HITS), synthesize=broken).run("q")
    assert "error" in out
    assert "off-contract" in out["error"]


def test_the_injected_synthesis_is_what_runs():
    def fixed(question, hits):
        return {"answer": "42", "sources": [], "confidence": 1.0}

    out = ResearchSubagent(kb=StubKB(HITS), synthesize=fixed).run("q")
    assert out == {"answer": "42", "sources": [], "confidence": 1.0}


def test_research_tool_schema_shape():
    assert RESEARCH_TOOL["name"] == "research_policy"
    props = RESEARCH_TOOL["input_schema"]["properties"]
    assert props["question"]["type"] == "string"
    assert RESEARCH_TOOL["input_schema"]["required"] == ["question"]


# ---------------------------------------------------------------------------
# Loop integration: the model delegates to the subagent
# ---------------------------------------------------------------------------

def _text(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use(name, input_, tid="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=tid)


def _response(*blocks):
    return SimpleNamespace(content=list(blocks))


@patch("scoutbot.loop._client")
def test_loop_delegates_a_policy_question_to_the_subagent(mock_client):
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Let me check the policy."), _tool_use("research_policy", {"question": "refund window?"})),
        _response(_text("Refunds take five business days.")),
    ]
    agent = ResearchSubagent(kb=StubKB(HITS))

    result = run_agent_loop("When will my refund arrive?", customer_id="1001", subagent=agent)

    assert result.steps[0].action == "research_policy"
    assert result.steps[0].observation["answer"].startswith("Refunds are issued")
    assert result.steps[0].observation["confidence"] == 0.88


@patch("scoutbot.loop._client")
def test_research_tool_is_not_offered_without_a_subagent(mock_client):
    mock_client.return_value.messages.create.side_effect = [_response(_text("Nothing to do."))]
    run_agent_loop("hi", customer_id="1001")
    _, kwargs = mock_client.return_value.messages.create.call_args
    tool_names = {t["name"] for t in kwargs["tools"]}
    assert "research_policy" not in tool_names
