"""Week 10 Day 5: the whole modern stack, wired into one run.

All week, each new piece arrived on its own and proved itself in its own demo: an MCP client (Day 1), an
MCP server (Day 2), pre/post-tool-use hooks and a research subagent (Day 3), a type-safe triage agent
(Day 4). Today nothing new is invented - the day is the *assembly*, and the point it teaches is that a
production agent is a **composition of small, independently-testable patterns**, not one monolith.

The happy accident that makes this short: `run_agent_loop` was designed additively from the start, so it
*already* accepts every collaborator this week produced - `mcp`, `hooks`, `ledger`, `subagent`, plus the
`log_path` trace from Week 8. This module adds the one thing the loop does not do on its own: the Day 4
typed-agent triage, run *first*. That is the shape of a real ticket handler and the integration pattern in
one sentence: **classify with a contract, then resolve with tools** - under guards, an audit, an
idempotent ledger, a delegate, and a trace.

Two seams keep the whole thing testable, exactly as every prior week's did:
- `assemble_stack(...)` takes each collaborator as an argument with a safe default, so a test can swap in a
  stub knowledge base, an in-memory ledger, a fake approver, or an in-memory MCP provider.
- `resolve_ticket(..., triage_model=...)` passes a model to the typed agent, so tests drive triage with a
  `TestModel`/`FunctionModel` (never a real call), and the loop's own `_client` seam is patched the same
  way it has been since Week 7.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from .hooks import Hooks, audit_hook, refund_guard
from .loop import AgentResult, run_agent_loop
from .mcp_client import MCPToolProvider
from .notify import Ledger
from .schema import TicketTriage
from .subagent import ResearchSubagent
from .tools import look_up_customer
from .typed_agent import triage as typed_triage


@dataclass
class Stack:
    """The week's collaborators, assembled for one wired run.

    Built once by `assemble_stack` and handed to `resolve_ticket`. Holding them together in one object is
    itself the lesson: these are the seams a production agent is composed of - a guard-and-audit pair, an
    idempotent ledger, an optional delegate, an optional set of tools reached over a protocol, and the
    approver the guards defer to.
    """

    hooks: Hooks
    ledger: Ledger
    approve_fn: Optional[Callable[[str], bool]] = None
    subagent: Optional[ResearchSubagent] = None
    mcp: Optional[MCPToolProvider] = None
    audit_trail: list = field(default_factory=list)


@dataclass
class StackResult:
    """What one end-to-end run produced: the contract-driven triage up front, the loop's resolution, and
    the audit trail of every guarded tool call in between. Everything the day integrates, in one object."""

    triage: TicketTriage
    result: AgentResult
    audit_trail: list


def assemble_stack(
    kb=None,
    approve_fn: Optional[Callable[[str], bool]] = None,
    ledger: Optional[Ledger] = None,
    mcp: Optional[MCPToolProvider] = None,
    get_customer: Callable[[str], dict] = look_up_customer,
) -> Stack:
    """Wire the week's pieces into one `Stack`, each collaborator injectable, each with a safe default.

    - `kb`: a knowledge base for the research subagent. `None` (the default) means no delegate is wired,
      and the `research_policy` tool simply is not offered - the same "not offered without its
      collaborator" rule the loop already follows for the refund tool.
    - `approve_fn`: the human approver the refund guard (and the loop's escalation) defer to. `None`
      behaves as "no human available", so anything needing approval is blocked - the safe default.
    - `ledger`: the idempotency ledger that makes `issue_refund` available *and* at-most-once. Defaults to
      a fresh in-memory ledger; pass a durable one (`Ledger`) for a real run.
    - `mcp`: an `MCPToolProvider` whose tools the model may also call. `None` runs with native + server
      tools only.
    - `get_customer`: how the refund guard looks up a customer's billing facts (plan, recent refunds).
      Defaults to the real `look_up_customer`; tests pass a dict-backed stub.
    """
    ledger = ledger or Ledger.in_memory()
    trail: list = []
    hooks = Hooks(
        pre=[refund_guard(get_customer, approve_fn=approve_fn)],
        post=[audit_hook(trail)],
    )
    subagent = ResearchSubagent(kb=kb) if kb is not None else None
    return Stack(
        hooks=hooks,
        ledger=ledger,
        approve_fn=approve_fn,
        subagent=subagent,
        mcp=mcp,
        audit_trail=trail,
    )


def resolve_ticket(
    stack: Stack,
    ticket_text: str,
    customer_id: str,
    ticket_id: Optional[str] = None,
    triage_model=None,
    log_path=None,
    max_steps: int = 6,
) -> StackResult:
    """Run one ticket through the whole stack: classify with a contract, then resolve with tools.

    Step 1 - **classify**: the Day 4 typed agent returns a validated `TicketTriage` (category, priority,
    owner), the framework enforcing the contract and retrying on a miss. `triage_model` is for tests
    (`TestModel`/`FunctionModel`); leave it `None` to use the real model.

    Step 2 - **resolve**: the fully-wired loop takes over, with the stack's MCP tools (Day 1), guarded and
    audited tool calls (Day 3), the idempotent refund ledger (Day 3 / Week 8), the research delegate
    (Day 3), and an optional trace (Week 8). The same `approve_fn` the refund guard uses is handed to the
    loop for escalation, so one human decision-maker serves both gates.

    Returns a `StackResult` bundling the triage, the loop's `AgentResult`, and the audit trail.
    """
    triage = typed_triage(ticket_text, model=triage_model)
    result = run_agent_loop(
        ticket_text,
        customer_id,
        max_steps=max_steps,
        approve_fn=stack.approve_fn,
        ticket_id=ticket_id,
        log_path=log_path,
        mcp=stack.mcp,
        hooks=stack.hooks,
        ledger=stack.ledger,
        subagent=stack.subagent,
    )
    return StackResult(triage=triage, result=result, audit_trail=stack.audit_trail)
