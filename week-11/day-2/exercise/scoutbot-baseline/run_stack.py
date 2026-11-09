"""Week 10, the finale in one script: the whole stack resolving one ticket.

Everything the week built, wired together and run once:

  - Day 4  a typed agent triages the ticket into a validated TicketTriage (category, priority, owner);
  - Day 1  an MCP client makes an external order-status tool callable, over the protocol;
  - Day 3  pre/post-tool-use hooks guard and audit every client tool the loop runs;
  - Day 3  a research subagent is available to answer a scoped policy question under a contract;
  - Wk 8   an idempotent ledger keeps a refund to at-most-once;
  - Wk 8   a trace records every step to a JSONL file.

`stack.assemble_stack(...)` wires the collaborators; `stack.resolve_ticket(...)` runs the pattern -
classify with a contract, then resolve with tools. Watch one ticket flow through all of it: the triage
contract up front, then each loop step (including any guarded refund and the MCP order-status call), then
the audit trail of every tool call, then the final answer.

This makes real Anthropic calls (the triage agent and the loop), so it needs `ANTHROPIC_API_KEY`. The
*offline* proof that the pieces compose is `tests/test_stack.py`, which drives the whole path with fake
models and stubs and never touches the network. The order-status MCP server is fully local.

    python run_stack.py
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

from scoutbot.knowledge import KnowledgeBase, fastembed_embedder
from scoutbot.mcp_client import stdio_provider
from scoutbot.stack import assemble_stack, resolve_ticket

load_dotenv()

HERE = Path(__file__).parent
ORDER_SERVER = HERE / "order_status_server.py"
CORPUS_DIR = HERE / "knowledge_base"
KB_PATH = HERE / "knowledge.db"
TRACE_PATH = HERE / "stack_run.jsonl"

# One customer, one ticket that touches several seams at once: it needs the account (look_up_customer),
# it asks for a refund large enough to trip the guard, and it references an order the external MCP tool
# can check. Customer 1001 is a pro account with a couple of recent refunds (see mock_customers.json), so
# a big refund needs a manager - and our approver below says yes, so it goes through and is ledgered once.
TICKET_ID = "T-5001"
CUSTOMER_ID = "1001"
TICKET = (
    "I was double-charged EUR 900 on my last invoice and I want it refunded. "
    "Also, where is my order ORD-1042? It has been days."
)


def _build_kb() -> KnowledgeBase:
    embed = fastembed_embedder()
    if KB_PATH.exists() and KnowledgeBase(embed, db_path=KB_PATH).count() > 0:
        return KnowledgeBase(embed, db_path=KB_PATH)
    return KnowledgeBase.build(CORPUS_DIR, embed, db_path=KB_PATH)


def main() -> None:
    # The one human in the loop: a manager who approves this refund. The refund guard and the loop's
    # escalation both defer to this same function - one decision-maker, two gates.
    def approve(reason: str) -> bool:
        print(f"  [human] approval requested: {reason}\n  [human] -> approved")
        return True

    kb = _build_kb()  # first run downloads the embedding model and builds knowledge.db, once
    mcp = stdio_provider(sys.executable, [str(ORDER_SERVER)])
    print(f"Connected to MCP server: {[t['name'] for t in mcp.tool_schemas()]}\n")

    stack = assemble_stack(kb=kb, approve_fn=approve, mcp=mcp)

    print(f"=== {TICKET_ID}: {TICKET} ===\n")
    outcome = resolve_ticket(
        stack, TICKET, customer_id=CUSTOMER_ID, ticket_id=TICKET_ID, log_path=TRACE_PATH
    )

    t = outcome.triage
    print("Triage (Day 4 typed contract):")
    print(f"  category={t.category.value}  priority={t.priority.value}  owner={t.suggested_owner}\n")

    print("Loop steps (Day 1 MCP + Day 3 guards):")
    for i, step in enumerate(outcome.result.steps, start=1):
        if step.action:
            print(f"  step {i}: {step.action}({step.action_input}) -> {step.observation}")
        else:
            print(f"  step {i}: (final) {step.thought}")

    print("\nAudit trail (Day 3 post-hook - every tool call, blocked or not):")
    for record in outcome.audit_trail:
        obs = record["observation"]
        verdict = "BLOCKED" if obs.get("blocked") else ("skipped" if obs.get("skipped") else "ran")
        print(f"  {record['tool']}({record['args']}) -> {verdict}")

    print("\nLedger (Wk 8 - money actually moved):")
    for key, detail, _ in stack.ledger.entries():
        print(f"  {key}: {detail}")

    print(f"\nFinal answer: {outcome.result.final_answer}")
    print(f"Trace written to {TRACE_PATH.name} (one JSON line per step).")
    print("\nOne ticket, the whole stack: a typed contract, an MCP tool, a guarded refund, an audit, a trace.")


if __name__ == "__main__":
    main()
