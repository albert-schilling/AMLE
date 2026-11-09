"""Week 10 Day 5: the whole stack composes, tested offline.

This is the integration test for the week. It proves that the pieces built on separate days - a typed
triage agent, an MCP tool, guard-and-audit hooks, an idempotent ledger, a research subagent - actually
fit together in one `resolve_ticket` run, and it does so with **no key and no network**. Two seams make
that possible, the same two every prior week used:

- the typed agent takes its model at call time, so triage is driven by a `TestModel`; and
- the loop's `_client` is patched, so the resolution turns are scripted rather than real.

The MCP provider here is a tiny fake (duck-typed to the three methods the loop calls), so even the
"reached over a protocol" seam is exercised without spawning a server.
"""
import pydantic_ai.models as pai_models

# The hard offline backstop, in case this module runs before test_typed_agent sets it. TestModel is
# exempt; a real triage request would raise rather than reach the network.
pai_models.ALLOW_MODEL_REQUESTS = False

from types import SimpleNamespace
from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from scoutbot.notify import Ledger
from scoutbot.schema import Category, Priority, TicketTriage
from scoutbot.stack import Stack, StackResult, assemble_stack, resolve_ticket


# --- fakes and helpers -----------------------------------------------------

def _hit(source, text, score):
    return SimpleNamespace(source=source, text=text, score=score)


class StubKB:
    """A knowledge base with a fixed hit list - no embedder, no SQLite (see test_subagent.py)."""

    def __init__(self, hits):
        self._hits = hits

    def search(self, query, *, k=3):
        return self._hits[:k]


class FakeMCP:
    """A stand-in MCPToolProvider: the three methods the loop actually calls, no server process."""

    def tool_schemas(self):
        return [{
            "name": "get_order_status",
            "description": "Look up the delivery status of an order.",
            "input_schema": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        }]

    def has_tool(self, name):
        return name == "get_order_status"

    def call(self, name, args):
        return {"found": True, "order_id": args["order_id"], "status": "shipped"}


def _triage_model(category="billing", priority="high", owner="billing-team"):
    return TestModel(custom_output_args={
        "category": category, "priority": priority, "suggested_owner": owner,
    })


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use(name, input_, tid="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=tid)


def _response(*blocks):
    return SimpleNamespace(content=list(blocks))


HITS = [_hit("refunds", "Refunds are issued within five business days.", 0.88)]


# --- assemble_stack: the wiring -------------------------------------------

def test_assemble_stack_defaults_are_safe():
    stack = assemble_stack()
    assert isinstance(stack, Stack)
    assert stack.subagent is None          # no kb -> no delegate wired
    assert stack.mcp is None
    assert isinstance(stack.ledger, Ledger)  # a fresh in-memory ledger by default
    assert stack.hooks.pre and stack.hooks.post  # guard + audit always wired
    assert stack.audit_trail == []


def test_assemble_stack_wires_a_subagent_only_when_a_kb_is_given():
    assert assemble_stack(kb=None).subagent is None
    assert assemble_stack(kb=StubKB(HITS)).subagent is not None


# --- resolve_ticket: classify, then resolve --------------------------------

@patch("scoutbot.loop._client")
def test_resolve_ticket_triages_then_resolves(mock_client):
    # The loop looks the customer up, then answers. Triage is driven by a TestModel (no real call).
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Checking the account."), _tool_use("look_up_customer", {"customer_id": "1001"})),
        _response(_text("You're on the Pro plan; all set.")),
    ]
    stack = assemble_stack(approve_fn=lambda r: True)

    outcome = resolve_ticket(stack, "What plan am I on?", customer_id="1001", triage_model=_triage_model())

    assert isinstance(outcome, StackResult)
    # Step 1: the Day 4 typed contract.
    assert isinstance(outcome.triage, TicketTriage)
    assert outcome.triage.category is Category.billing and outcome.triage.priority is Priority.high
    # Step 2: the loop resolved it, and the audit trail witnessed the tool call.
    assert outcome.result.final_answer.startswith("You're on the Pro plan")
    assert outcome.audit_trail[0]["tool"] == "look_up_customer"


@patch("scoutbot.loop._client")
def test_stack_guards_an_unapproved_refund_and_moves_no_money(mock_client):
    # Customer 1001 is a pro account with recent refunds; a EUR 900 refund needs a manager. The approver
    # says no, so the guard blocks it - end to end, through the assembled stack.
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Refunding."), _tool_use("issue_refund", {"customer_id": "1001", "amount": 900})),
        _response(_text("That refund needs a manager, so I've flagged it.")),
    ]
    stack = assemble_stack(approve_fn=lambda reason: False)

    outcome = resolve_ticket(stack, "Refund me EUR 900", customer_id="1001", triage_model=_triage_model())

    assert outcome.result.steps[0].observation["blocked"] is True
    assert outcome.audit_trail[0]["observation"]["blocked"] is True  # the veto was audited
    assert stack.ledger.entries() == []  # no money moved


@patch("scoutbot.loop._client")
def test_stack_lets_an_approved_refund_through_once_and_dedupes_a_repeat(mock_client):
    # Approved this time; the model asks for the same refund twice, and the ledger keeps it to once.
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Refunding."), _tool_use("issue_refund", {"customer_id": "1001", "amount": 900})),
        _response(_text("Once more to be sure."), _tool_use("issue_refund", {"customer_id": "1001", "amount": 900}, tid="toolu_2")),
        _response(_text("Done - your refund is on its way.")),
    ]
    stack = assemble_stack(approve_fn=lambda reason: True)

    outcome = resolve_ticket(stack, "Refund me EUR 900", customer_id="1001", triage_model=_triage_model())

    assert outcome.result.steps[0].observation["issued"] is True
    assert outcome.result.steps[1].observation["skipped"] is True  # idempotent repeat
    assert len(stack.ledger.entries()) == 1  # the money moved exactly once


@patch("scoutbot.loop._client")
def test_stack_composes_an_mcp_tool(mock_client):
    # The MCP piece (Day 1) composes: an external get_order_status tool is offered and dispatched.
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Checking the order."), _tool_use("get_order_status", {"order_id": "ORD-1042"})),
        _response(_text("Your order ORD-1042 has shipped.")),
    ]
    stack = assemble_stack(mcp=FakeMCP(), approve_fn=lambda r: True)

    outcome = resolve_ticket(stack, "Where is ORD-1042?", customer_id="1001", triage_model=_triage_model())

    assert outcome.result.steps[0].action == "get_order_status"
    assert outcome.result.steps[0].observation["status"] == "shipped"
    # and the tool really was offered to the model, over the provider
    _, kwargs = mock_client.return_value.messages.create.call_args_list[0]
    assert "get_order_status" in {t["name"] for t in kwargs["tools"]}


@patch("scoutbot.loop._client")
def test_stack_composes_the_research_subagent(mock_client):
    # The delegate (Day 3) composes: research_policy is offered and returns a contracted result.
    mock_client.return_value.messages.create.side_effect = [
        _response(_text("Let me check policy."), _tool_use("research_policy", {"question": "refund window?"})),
        _response(_text("Refunds take five business days.")),
    ]
    stack = assemble_stack(kb=StubKB(HITS), approve_fn=lambda r: True)

    outcome = resolve_ticket(stack, "How long do refunds take?", customer_id="1001", triage_model=_triage_model())

    assert outcome.result.steps[0].action == "research_policy"
    assert outcome.result.steps[0].observation["answer"].startswith("Refunds are issued")
    _, kwargs = mock_client.return_value.messages.create.call_args_list[0]
    assert "research_policy" in {t["name"] for t in kwargs["tools"]}
