"""Week 11 Day 2, Topic 2: cost + latency metering, and the model-tiering lever.

The whole point of this module is that measuring what a run costs needs **no new dependency and no
new API**. Every Anthropic reply already carries a `usage` object (`response.usage`), and cost is a
`tokens x price` lookup against a small table you keep yourself. Latency is `time.perf_counter()`
around the call. That is the entire toolkit - the rest is discipline about where the numbers live.

Three things live here:

- `PRICING` + `cost_of` - the price table and the one function that turns a `Usage` into dollars.
- `Meter` - an accumulator that records one `CallRecord` per model call and totals cost, tokens, and
  latency across a run, so "what did this ticket cost?" is answerable after the fact (the same
  query-it-don't-re-run-it idea as Week 8's trace, one level up).
- `TIERS` + `pick_model` - **model tiering, the headline cost lever.** A cheap model handles the
  simple, high-volume work and a strong one is reserved for the hard tickets; choosing between them
  is a one-line model-name swap, not an architecture change.

`measure()` is the tiny latency timer, a context manager so a call reads
`with measure() as sw: resp = client.messages.create(...)` and `sw.ms` is the wall time after.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, List

from anthropic.types import Usage

MTOK = 1_000_000

# Per-million-token list prices in USD, confirmed against platform.claude.com on 2026-08-23.
# RE-CONFIRM THESE AT BUILD TIME - Anthropic changes them (Sonnet 5's launch price of $2/$10 was
# made permanent in Aug 2026, cancelling a scheduled rise to $3/$15). Keeping the table dated and in
# ONE place is the point: a stale constant buried in five call sites is how a cost model silently
# drifts wrong. `cache_write_5m` is the 5-minute cache-write rate; `cache_read` is the (much cheaper)
# cache-hit rate. Both only matter once prompt caching is on; base input/output cover every call today.
PRICING = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_write_5m": 1.25, "cache_read": 0.10},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_write_5m": 2.50, "cache_read": 0.20},
    "claude-opus-5": {"input": 5.00, "output": 25.00, "cache_write_5m": 6.25, "cache_read": 0.50},
}

# Model tiering: the single biggest lever on the bill. The cheap tier does the routine, high-volume
# work (routing, planning, easy tickets); the strong tier is spent only where difficulty earns it.
# Given `core.MODEL` reads from an env var, swapping tiers in production really is one name change.
TIERS = {"cheap": "claude-haiku-4-5", "strong": "claude-sonnet-5"}


class UnknownModelError(KeyError):
    """Raised when `cost_of` is asked to price a model that is not in `PRICING`.

    Deliberately loud: a missing price is a *wrong* cost report, not a zero-cost one, and a silent
    `$0.00` is exactly the kind of number that gets trusted in a budget review. Add the model to
    `PRICING` (with a dated source) rather than defaulting it to free.
    """


def pick_model(difficulty: str) -> str:
    """Map a ticket's assessed difficulty to a model name. `hard` earns the strong tier; everything
    else gets the cheap one. The safe default is cheap: over-spending on an easy ticket is the waste
    the whole topic exists to cut, so anything not explicitly `hard` stays on Haiku."""
    return TIERS["strong"] if difficulty == "hard" else TIERS["cheap"]


def cost_of(usage: Usage, model: str) -> float:
    """Turn one reply's `usage` into a dollar figure against `PRICING[model]`.

    Reads the four token counts Anthropic reports - base input, output, and the two cache counters -
    and prices each at its own rate. `cache_creation_input_tokens`/`cache_read_input_tokens` are
    `None` on a call that used no caching, so they default to 0 and simply contribute nothing. Raises
    `UnknownModelError` for a model with no price rather than returning a misleading $0.00.
    """
    if model not in PRICING:
        raise UnknownModelError(
            f"No price for {model!r}. Add it to metering.PRICING (with a dated source) - a missing "
            "price silently reports $0.00, which is worse than crashing."
        )
    rate = PRICING[model]
    base_in = usage.input_tokens or 0
    out = usage.output_tokens or 0
    cache_write = usage.cache_creation_input_tokens or 0
    cache_read = usage.cache_read_input_tokens or 0
    return (
        base_in * rate["input"]
        + out * rate["output"]
        + cache_write * rate["cache_write_5m"]
        + cache_read * rate["cache_read"]
    ) / MTOK


@dataclass
class CallRecord:
    """One model call's cost and timing - the flat, printable row a `Meter` collects.

    `label` names *which* call it was (`plan`, `draft`, ...) so a per-run report can show where the
    money and the milliseconds went, not just a single grand total.
    """

    label: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    latency_ms: float


@dataclass
class Meter:
    """A per-run accumulator of `CallRecord`s. Answers 'what did this ticket cost, and where?'.

    Deliberately just a list plus a few sums - the same 'a plain object, not a service' choice as
    Week 8's `Ledger`. Pass one `Meter` down through a run (`plan_ticket(..., meter=meter)`), and
    every model call appends a row; at the end `report()` prints the breakdown and `total_cost` /
    `total_tokens` / `total_latency_ms` give the roll-ups a test or a dashboard can assert on.
    """

    calls: List[CallRecord] = field(default_factory=list)

    def record(self, label: str, model: str, usage: Usage, latency_ms: float) -> CallRecord:
        """Price one call, append its row, and return it (handy for a caller that wants to log it)."""
        rec = CallRecord(
            label=label,
            model=model,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_tokens=usage.cache_read_input_tokens or 0,
            cost_usd=cost_of(usage, model),
            latency_ms=round(latency_ms, 1),
        )
        self.calls.append(rec)
        return rec

    @property
    def total_cost(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.input_tokens + c.output_tokens for c in self.calls)

    @property
    def total_latency_ms(self) -> float:
        return round(sum(c.latency_ms for c in self.calls), 1)

    def report(self) -> str:
        """A short human-readable breakdown: one line per call, then the totals.

        Costs are shown to 6 decimals on purpose - a single Haiku call is fractions of a cent, and
        rounding it to `$0.00` would hide exactly the per-call figure students need to reason about
        volume ('$0.0006 x 50k tickets/day' is the sentence that makes tiering matter)."""
        lines = [f"{'call':<10} {'model':<18} {'in':>7} {'out':>6} {'cost($)':>10} {'ms':>8}"]
        for c in self.calls:
            lines.append(
                f"{c.label:<10} {c.model:<18} {c.input_tokens:>7} {c.output_tokens:>6} "
                f"{c.cost_usd:>10.6f} {c.latency_ms:>8.1f}"
            )
        lines.append(
            f"{'TOTAL':<10} {'':<18} {'':>7} {'':>6} {self.total_cost:>10.6f} {self.total_latency_ms:>8.1f}"
        )
        return "\n".join(lines)


@dataclass
class _Stopwatch:
    """Filled in by `measure()` on exit; `.ms` is the elapsed wall time in milliseconds."""

    ms: float = 0.0


@contextmanager
def measure() -> Iterator[_Stopwatch]:
    """Time the block it wraps. `with measure() as sw: ...` then read `sw.ms` afterwards.

    Uses `perf_counter` (a monotonic clock meant for durations) rather than `time.time()`, so a
    system-clock adjustment mid-call can never produce a negative or wildly wrong latency. This is
    all 'measure latency' needs - the honest wall time each call took, from the caller's side.
    """
    sw = _Stopwatch()
    start = time.perf_counter()
    try:
        yield sw
    finally:
        sw.ms = (time.perf_counter() - start) * 1000
