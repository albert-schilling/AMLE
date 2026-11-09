"""Week 11 Day 2 demo: the cost + tiering lever, made concrete - and it runs with NO API key.

The point of the day's second topic is that you can reason about a bill without spending a cent: cost is
`tokens x price`, and the token counts come off `response.usage` on runs you have already done. So this
demo takes *recorded* usage numbers (the shape a real planning call returns) and shows three things:

1. a per-call cost/latency report through a `Meter`;
2. the **tiering comparison** - the exact same tokens priced on the cheap tier vs the strong one; and
3. the **volume projection** that makes tiering matter - a fraction of a cent, times a day's tickets.

Nothing here calls the model. `run_planner.py` is the live version that does.
"""
from anthropic.types import Usage

from scoutbot.metering import Meter, cost_of

# Recorded usage from three representative planning calls (in/out tokens as `messages.create` reported
# them). A planning call is small: a system prompt plus a short ticket in, a one-line tool call out.
RECORDED = [
    ("plan:simple", Usage(input_tokens=780, output_tokens=18)),
    ("plan:refund", Usage(input_tokens=812, output_tokens=24)),
    ("plan:multi", Usage(input_tokens=905, output_tokens=41)),
]

DAILY_TICKETS = 50_000


def main() -> None:
    print("Per-call cost + (recorded) latency, planned on the cheap tier (Haiku 4.5):")
    meter = Meter()
    for i, (label, usage) in enumerate(RECORDED):
        meter.record(label, "claude-haiku-4-5", usage, latency_ms=290.0 + i * 30)
    print(meter.report())

    print("\nSame tokens, cheap tier vs strong tier - the tiering lever:")
    print(f"  {'call':<12} {'haiku($)':>12} {'sonnet($)':>12} {'x more':>8}")
    for label, usage in RECORDED:
        cheap = cost_of(usage, "claude-haiku-4-5")
        strong = cost_of(usage, "claude-sonnet-5")
        print(f"  {label:<12} {cheap:>12.6f} {strong:>12.6f} {strong / cheap:>7.1f}x")

    avg_cheap = sum(cost_of(u, "claude-haiku-4-5") for _, u in RECORDED) / len(RECORDED)
    avg_strong = sum(cost_of(u, "claude-sonnet-5") for _, u in RECORDED) / len(RECORDED)
    print(f"\nProjected planning spend at {DAILY_TICKETS:,} tickets/day (one plan each):")
    print(f"  all-Haiku : ${avg_cheap * DAILY_TICKETS:,.2f}/day  (~${avg_cheap * DAILY_TICKETS * 30:,.0f}/mo)")
    print(f"  all-Sonnet: ${avg_strong * DAILY_TICKETS:,.2f}/day  (~${avg_strong * DAILY_TICKETS * 30:,.0f}/mo)")
    print("  -> tiering means paying the Sonnet rate only on the tickets that earn it, not all of them.")


if __name__ == "__main__":
    main()
