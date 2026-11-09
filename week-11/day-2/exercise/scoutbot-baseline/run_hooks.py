"""Week 10 Day 3, the hooks half in one script: a guard before a tool, an audit after it.

Runs fully offline - no Anthropic key - because the point is the *guard*, not the reasoning. It drives
`run_hooked` directly with the `issue_refund` tool, the same way the loop does, and shows four things:

  1. a small refund on a clean account runs with nobody interrupted;
  2. a large refund is blocked, because the guard asks the policy and the (simulated) approver says no;
  3. the same large refund, with approval granted, goes through;
  4. issuing it again is a no-op - the ledger keeps money to once.

Every call, allowed or blocked, is recorded by the audit post-hook, and the trail is printed at the
end. That is the whole day: a pre-hook that can veto, a post-hook that can only witness.

    python run_hooks.py
"""
from scoutbot.hooks import Hooks, audit_hook, refund_guard, run_hooked
from scoutbot.notify import Ledger
from scoutbot.tools import issue_refund

# The customer records the guard consults. These are billing *facts* - the plan and the recent refund
# count come from the account, never from what a customer or the model typed.
CUSTOMERS = {
    "1001": {"plan": "pro", "past_refunds_90d": 0},   # clean account
    "1004": {"plan": "free", "past_refunds_90d": 4},  # repeat refunder
}


def get_customer(customer_id):
    return CUSTOMERS.get(customer_id, {})


def main():
    ledger = Ledger.in_memory()
    trail = []

    def hooks_for(approver_says_yes: bool) -> Hooks:
        return Hooks(
            pre=[refund_guard(get_customer, approve_fn=lambda reason: approver_says_yes)],
            post=[audit_hook(trail)],
        )

    def refund(customer_id, amount, hooks):
        return run_hooked(
            "issue_refund",
            {"customer_id": customer_id, "amount": amount},
            lambda: issue_refund(customer_id, amount, ledger=ledger),
            hooks,
        )

    print("1) Small refund on a clean account (under the limit, no human needed):")
    print("   ", refund("1001", 20, hooks_for(approver_says_yes=False)), "\n")

    print("2) Large refund, approver says NO -> blocked before any money moves:")
    print("   ", refund("1001", 900, hooks_for(approver_says_yes=False)), "\n")

    print("3) Same large refund, approver says YES -> it goes through:")
    print("   ", refund("1001", 900, hooks_for(approver_says_yes=True)), "\n")

    print("4) Issue that approved refund again -> the ledger keeps it to once:")
    print("   ", refund("1001", 900, hooks_for(approver_says_yes=True)), "\n")

    print("Audit trail (one line per tool call, blocked or not):")
    for record in trail:
        obs = record["observation"]
        verdict = "BLOCKED" if obs.get("blocked") else ("SKIPPED" if obs.get("skipped") else "issued")
        print(f"   {record['tool']}({record['args']}) -> {verdict}")

    print("\nLedger (money actually moved):")
    for key, detail, _ in ledger.entries():
        print(f"   {key}: {detail}")


if __name__ == "__main__":
    main()
