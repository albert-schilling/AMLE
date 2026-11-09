"""Guards around tool calls: run something *before* a tool, and *after* it.

Weeks 7-10 gave ScoutBot more and more tools, and Week 10 let it call tools it did not even write
(over MCP). Autonomy is the point - but an autonomous agent calling a tool that *moves money* is a
different thing from one that looks a customer up. Today adds the seam where a tool call can be
inspected, blocked, or recorded before and after it runs, without touching the tool itself or the
loop's control flow. That seam is a **hook.**

Two kinds, and they are deliberately asymmetric:

- **A pre-tool-use hook is a guard.** It sees the pending call - the tool name and its arguments -
  *before* the tool runs, and it can veto: return a replacement observation (a dict) to block the
  call, or return `None` to let it through. This is where the refund guard lives (see
  `refund_guard`): a refund over the policy limit does not run unless a human approves it, and the
  model never gets to route around that, because the check is not in the prompt, it is in the code
  path every call passes through.
- **A post-tool-use hook is a witness.** It sees the finished call - name, arguments, and the
  observation the tool returned - *after* it runs, and returns nothing. It cannot change what
  happened; it records it. This is where the audit trail lives (see `audit_hook`): one line per tool
  call, whatever the tool, whoever wrote it.

The whole mechanism is `run_hooked` below. It is intentionally tiny - pre-hooks first, then the
tool, then post-hooks - because the value is *where* it sits (around every tool the loop runs),
not how clever it is. Note the one honest limit up front: server tools (web_fetch, code_execution)
run inside Anthropic's infrastructure before this code ever sees them, so a hook here cannot guard
those. It guards the client tools this loop dispatches itself - including the dangerous one added
today, `issue_refund`.
"""
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .policy import decide_approval

# A pre-tool-use hook inspects a pending call (name, args). Return a dict to BLOCK the call - that
# dict becomes the observation the model sees, exactly as if the tool had returned it - or return
# None to allow the call through to the next hook and finally the tool.
PreHook = Callable[[str, dict], Optional[dict]]

# A post-tool-use hook observes a completed call (name, args, observation). It is for side effects
# only - audit, logging, metrics - and returns nothing. It runs on blocked calls too, so the audit
# trail records the veto as faithfully as it records the action.
PostHook = Callable[[str, dict, dict], None]


@dataclass
class Hooks:
    """The two hook lists the loop runs around each client tool call. Both default empty, so a loop
    given no hooks behaves exactly as it did before today."""

    pre: List[PreHook] = field(default_factory=list)
    post: List[PostHook] = field(default_factory=list)


def run_hooked(name: str, args: dict, execute: Callable[[], dict], hooks: Optional[Hooks]) -> dict:
    """Run `execute()` (the actual tool dispatch) wrapped in pre- and post-tool-use hooks.

    The order is the whole design: every pre-hook gets a chance to veto first; the first one that
    returns a dict short-circuits, and the tool never runs. Otherwise the tool runs, and every
    post-hook witnesses the result. Post-hooks fire on the blocked path too, so an audit trail sees
    the veto - a refund that was *stopped* is exactly the event you want recorded.

    `hooks=None` means "no guards": `execute()` runs unwrapped, which is byte-for-byte the behaviour
    of every day before this one.
    """
    if hooks is None:
        return execute()

    for pre in hooks.pre:
        blocked = pre(name, args)
        if blocked is not None:
            _run_post(name, args, blocked, hooks)
            return blocked

    observation = execute()
    _run_post(name, args, observation, hooks)
    return observation


def _run_post(name: str, args: dict, observation: dict, hooks: Hooks) -> None:
    for post in hooks.post:
        post(name, args, observation)


def refund_guard(
    get_customer: Callable[[str], dict],
    approve_fn: Optional[Callable[[str], bool]] = None,
    decide=decide_approval,
) -> PreHook:
    """A pre-tool-use hook that gates `issue_refund` on the refund policy (see `policy.py`).

    It only ever fires for the `issue_refund` tool; every other tool passes straight through
    (returns `None`). For a refund, it looks the customer up as a *billing fact* - the plan and the
    recent refund count come from the account record, never from what the model typed - and asks the
    same `decide_approval` table Week 8 Day 4 built whether a human is needed. If one is, and the
    injected `approve_fn` does not grant it, the call is blocked with an observation the model reads
    like any other: the refund did not happen, and here is which approver it needs and why.

    This is the point of doing it as a hook rather than a sentence in the system prompt: the model
    cannot talk its way past a code path. The amount and the account history decide, in code, on
    every call.
    """
    def hook(name: str, args: dict) -> Optional[dict]:
        if name != "issue_refund":
            return None
        amount = float(args.get("amount") or 0.0)
        customer = get_customer(args.get("customer_id", "")) or {}
        approval = decide(
            amount=amount,
            plan=str(customer.get("plan") or "unknown"),
            past_refunds_90d=int(customer.get("past_refunds_90d") or 0),
            priority="",  # the tool call carries no triage priority; amount and history decide here
        )
        if approval.needs_human:
            approve = approve_fn or (lambda reason: False)
            if not approve(approval.reason):
                return {
                    "issued": False,
                    "blocked": True,
                    "reason": f"needs {approval.approver}: {approval.reason}",
                }
        return None

    return hook


def audit_hook(sink: list) -> PostHook:
    """A post-tool-use hook that appends one record per tool call to `sink`.

    Deliberately dumb: it records *every* client tool call the loop makes - the tool's name, the
    arguments, and the observation it returned (or the block it was given) - so the audit trail is
    one flat list you can print, assert on, or write to a log. Because it is a post-hook it cannot
    change anything; it only witnesses, which is exactly what an audit trail should be able to do
    and no more.
    """
    def hook(name: str, args: dict, observation: dict) -> None:
        sink.append({"tool": name, "args": args, "observation": observation})

    return hook
