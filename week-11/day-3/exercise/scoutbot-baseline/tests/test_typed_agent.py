"""Offline tests for the Pydantic AI triage agent.

The whole point of Day 4's design is that these run with no key and no network. Two things make that
true, and this file exercises both:

- A hard backstop: `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False`, set once at import below. If any
  test accidentally triggers a *real* model request, the framework raises instead of reaching Anthropic.
- Fake models passed at call time: `TestModel` (auto-generates a schema-valid result, or takes
  `custom_output_args`) and `FunctionModel` (a function we write that returns exactly the model response
  we want, so we can script a bad-then-good retry). Neither is a real request, so both are exempt from
  the backstop above.
"""
import pydantic_ai.models as pai_models

# The hard offline backstop, set before anything runs a model. TestModel/FunctionModel are exempt; a
# real AnthropicModel request is not - which is exactly what test_backstop_blocks_a_real_model checks.
pai_models.ALLOW_MODEL_REQUESTS = False

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from scoutbot.schema import Category, Priority, TicketTriage
from scoutbot.typed_agent import triage, triage_agent


def _output_tool_name(info: AgentInfo) -> str:
    """Pydantic AI registers one output tool for `output_type=TicketTriage`; it is named 'final_result'."""
    return info.output_tools[0].name


def test_agent_has_no_bound_model_so_import_is_key_free():
    # The agent is constructed with no model, which is what lets `import scoutbot.typed_agent` work with
    # no ANTHROPIC_API_KEY. The model is supplied at call time instead.
    assert triage_agent.model is None


def test_triage_returns_validated_ticket_triage_with_testmodel():
    model = TestModel(
        custom_output_args={
            "category": "billing",
            "priority": "high",
            "suggested_owner": "billing-team",
        }
    )
    result = triage("I was charged twice, please refund the extra charge.", model=model)

    assert isinstance(result, TicketTriage)
    assert result.category is Category.billing
    assert result.priority is Priority.high
    assert result.suggested_owner == "billing-team"


def test_testmodel_default_output_is_schema_valid():
    # With no custom args, TestModel synthesises data that satisfies the output schema - so even the
    # "I didn't script anything" path yields a valid TicketTriage (enum members, a string owner).
    result = triage("anything at all", model=TestModel())

    assert isinstance(result, TicketTriage)
    assert result.category in Category
    assert result.priority in Priority
    assert isinstance(result.suggested_owner, str)


def test_schema_miss_is_retried_then_recovers():
    # First reply is schema-invalid (priority 'urgent!!' is not in the Priority enum); the framework
    # re-prompts, and the second reply validates. Same behaviour as Week 7's hand-rolled retry - but the
    # framework owns the loop.
    calls = {"n": 0}

    def bad_then_good(messages, info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        name = _output_tool_name(info)
        if calls["n"] == 1:
            args = {"category": "billing", "priority": "urgent!!", "suggested_owner": "billing-team"}
        else:
            args = {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}
        return ModelResponse(parts=[ToolCallPart(tool_name=name, args=args)])

    result = triage("flaky first reply", model=FunctionModel(bad_then_good))

    assert result.priority is Priority.high
    assert calls["n"] == 2  # retried exactly once, then succeeded


def test_output_validator_forces_a_retry_on_a_bad_owner():
    # The reply is schema-valid but the owner is a sentence, not a handle. The output validator raises
    # ModelRetry, the framework re-prompts, and the second reply is a proper handle. Types check the
    # form; the validator checks the sense - both on the one retry loop.
    calls = {"n": 0}

    def sentence_then_handle(messages, info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        name = _output_tool_name(info)
        owner = "the billing people, probably" if calls["n"] == 1 else "billing-team"
        args = {"category": "billing", "priority": "high", "suggested_owner": owner}
        return ModelResponse(parts=[ToolCallPart(tool_name=name, args=args)])

    result = triage("charged twice", model=FunctionModel(sentence_then_handle))

    assert result.suggested_owner == "billing-team"
    assert calls["n"] == 2


def test_output_validator_trims_a_valid_owner():
    # A handle with stray whitespace is acceptable - the validator normalises it rather than retrying.
    model = TestModel(
        custom_output_args={
            "category": "account",
            "priority": "low",
            "suggested_owner": "  account-team  ",
        }
    )
    result = triage("please close my account", model=model)

    assert result.suggested_owner == "account-team"


def test_exhausted_retries_raise_loudly():
    # Every reply is schema-invalid, so the one retry is spent and the framework raises rather than
    # returning a wrong or partial result - the framework's analogue of core.TriageError.
    forever_bad = TestModel(
        custom_output_args={"category": "billing", "priority": "urgent!!", "suggested_owner": "x"}
    )
    with pytest.raises(UnexpectedModelBehavior):
        triage("this never validates", model=forever_bad)


def test_backstop_blocks_a_real_model(monkeypatch):
    # With ALLOW_MODEL_REQUESTS = False (set at import), a *real* AnthropicModel request is refused
    # before any network call - the safety net that keeps an accidental real call out of the suite. A
    # dummy key only lets AnthropicModel construct; the guard fires before it would be used.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-dummy-not-real")
    from pydantic_ai.models.anthropic import AnthropicModel

    with pytest.raises(RuntimeError, match="ALLOW_MODEL_REQUESTS"):
        triage("this must never reach the network", model=AnthropicModel("claude-haiku-4-5"))
