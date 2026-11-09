"""Week 10 Day 4: ScoutBot's triage contract, now framework-native with Pydantic AI.

Week 7's `core.triage` did contract-driven output the hard way, and every line of it was plumbing:
hand-write the tool schema from the Pydantic model (`TicketTriage.model_json_schema()`), force the tool
call with `tool_choice`, pull the `tool_use` block out of the response, `model_validate` its input, and
retry once by hand in a `try/except`. It works - but the *contract* (a `TicketTriage`, validated) is
buried under the mechanics of getting one.

Pydantic AI collapses all of that into a single argument: `output_type=TicketTriage`. From that, the
framework derives the output tool's schema, requires the model to produce it, validates the reply against
the model, and re-prompts the model when validation fails. Same contract, same "retry once then fail
loud" behaviour - but the code says *what* it wants (a validated `TicketTriage`) instead of *how* to
coax and check one. That is the whole point of the day: type-safe, contract-driven output as a first
argument, not a hand-rolled loop.

The one non-obvious thing is keeping it **offline-testable**, and it is done the framework-native way:

- **The agent is built with NO bound model**, so importing this module needs no API key. Binding a
  provider string - `Agent("anthropic:claude-...")` - eagerly infers the provider and requires
  `ANTHROPIC_API_KEY` *at construction*, which would break a key-free import (and every offline test).
- **The real model is a lazy factory** (`anthropic_model()`), called only on the demo/production path,
  where a key exists. Constructing `AnthropicModel(...)` reads the key, so it must not happen at import.
- **Tests pass a fake model at call time** - `TestModel()` / `FunctionModel(fn)` via
  `triage(text, model=...)` or `triage_agent.override(model=...)` - and set
  `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` as a hard backstop: if a real request ever slips
  through, the framework raises rather than reaching the network.

The output contract is the *same* `schema.TicketTriage` the raw-SDK path uses - Day 4 changes the
machinery around the contract, never the contract itself.
"""
import os
from typing import Optional

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel

from .schema import TicketTriage

TRIAGE_SYSTEM_PROMPT = (
    "You triage a single customer-support ticket. Read the ticket and decide its category, its "
    "priority, and the team handle that should own it (for example 'billing-team'). Base every field "
    "on the ticket text alone, and produce the structured result you are asked for - nothing else."
)


# Built with NO bound model on purpose (see the module docstring): import stays key-free, so every test
# and a plain `import scoutbot.typed_agent` works with no environment at all. The model is supplied at
# call time. `retries=1` is the framework's version of Week 7's "retry once, then escalate": on a
# validation miss it re-prompts the model once, and if that also fails it raises UnexpectedModelBehavior.
triage_agent = Agent(
    output_type=TicketTriage,
    system_prompt=TRIAGE_SYSTEM_PROMPT,
    retries=1,
)


@triage_agent.output_validator
def owner_looks_like_a_team(result: TicketTriage) -> TicketTriage:
    """A domain rule the *type* cannot express: `suggested_owner` is a handle, not a sentence.

    `TicketTriage` guarantees the *shape* - three fields, category and priority from their enums. But
    `suggested_owner` is a free string, and "the billing people, probably" is a schema-valid answer that
    is still wrong. An output validator guards the *meaning*: raise `ModelRetry` and the framework
    re-prompts the model with the reason (bounded by the same `retries` budget), exactly as it does for a
    schema miss. Types check the form; validators check the sense; both ride one retry loop.
    """
    owner = result.suggested_owner.strip()
    if not owner or " " in owner:
        raise ModelRetry(
            "suggested_owner must be a single team handle like 'billing-team', "
            "not a blank or a sentence."
        )
    result.suggested_owner = owner
    return result


def anthropic_model(model_name: Optional[str] = None) -> AnthropicModel:
    """The real Anthropic model, built lazily so import needs no key.

    Constructing `AnthropicModel(...)` reads `ANTHROPIC_API_KEY`, so this is only ever called on the
    demo/production path - never at import, never in tests (which pass their own `TestModel`).
    """
    return AnthropicModel(model_name or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5"))


def triage(ticket_text: str, model: Optional[Model] = None) -> TicketTriage:
    """Classify one support ticket into a validated `TicketTriage`, the Pydantic AI way.

    Pass a `model` in tests (`TestModel()` / `FunctionModel(fn)`); leave it `None` to use the real
    Anthropic model via the lazy factory. The framework generates the output schema from `TicketTriage`,
    validates the model's reply, runs the output validators, and retries once on any miss. If it still
    fails it raises `pydantic_ai.exceptions.UnexpectedModelBehavior` - the framework's loud-failure
    analogue of `core.TriageError`, with no hand-written retry loop to maintain.
    """
    result = triage_agent.run_sync(ticket_text, model=model or anthropic_model())
    return result.output
