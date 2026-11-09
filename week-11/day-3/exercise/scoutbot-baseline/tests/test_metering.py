"""Week 11 Day 2, Topic 2: cost + latency metering, tested with no network and no clock stubs.

Cost is pure arithmetic off a real `anthropic` `Usage` object and the `PRICING` table, so these are
plain value assertions. Tiering is a lookup. `measure()` times a real (tiny) sleep, so it asserts a
lower bound rather than an exact figure - the honest thing to check about a wall-clock timer.
"""
import time

import pytest
from anthropic.types import Usage

from scoutbot.metering import (
    MTOK,
    PRICING,
    TIERS,
    CallRecord,
    Meter,
    UnknownModelError,
    cost_of,
    measure,
    pick_model,
)


# --- cost_of ---------------------------------------------------------------

def test_cost_of_prices_base_input_and_output():
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    # Haiku 4.5: $1 in + $5 out per MTok
    assert cost_of(usage, "claude-haiku-4-5") == pytest.approx(6.0)


def test_cost_of_scales_with_the_model_tier():
    usage = Usage(input_tokens=1200, output_tokens=300)
    # the same tokens cost strictly more on the strong tier - the reason tiering saves money
    assert cost_of(usage, "claude-sonnet-5") > cost_of(usage, "claude-haiku-4-5")


def test_cost_of_prices_cache_reads_cheaply():
    # a cached-read token is an order of magnitude cheaper than a fresh input token
    cached = Usage(input_tokens=0, output_tokens=0, cache_read_input_tokens=1_000_000)
    assert cost_of(cached, "claude-haiku-4-5") == pytest.approx(0.10)


def test_cost_of_treats_missing_cache_counters_as_zero():
    # a call with no caching reports None for the cache fields; that must contribute nothing, not crash
    usage = Usage(input_tokens=100, output_tokens=50)
    assert usage.cache_read_input_tokens is None
    assert cost_of(usage, "claude-haiku-4-5") == pytest.approx((100 * 1.0 + 50 * 5.0) / MTOK)


def test_cost_of_raises_on_an_unpriced_model():
    # a missing price must be loud - a silent $0.00 is a wrong budget number, not a free call
    with pytest.raises(UnknownModelError):
        cost_of(Usage(input_tokens=1, output_tokens=1), "claude-does-not-exist")


# --- model tiering ---------------------------------------------------------

def test_pick_model_reserves_the_strong_tier_for_hard_tickets():
    assert pick_model("hard") == TIERS["strong"] == "claude-sonnet-5"


def test_pick_model_defaults_to_cheap_for_anything_else():
    assert pick_model("easy") == TIERS["cheap"] == "claude-haiku-4-5"
    assert pick_model("") == "claude-haiku-4-5"  # unknown difficulty is safe-cheap, never silently strong


def test_every_tier_has_a_price():
    # a tier with no entry in PRICING would blow up only at runtime; catch it here
    for model in TIERS.values():
        assert model in PRICING


# --- Meter -----------------------------------------------------------------

def test_meter_accumulates_cost_tokens_and_latency_across_calls():
    meter = Meter()
    meter.record("plan", "claude-haiku-4-5", Usage(input_tokens=900, output_tokens=40), latency_ms=310.0)
    meter.record("draft", "claude-sonnet-5", Usage(input_tokens=1500, output_tokens=220), latency_ms=1800.0)
    assert len(meter.calls) == 2
    assert meter.total_tokens == 900 + 40 + 1500 + 220
    assert meter.total_latency_ms == pytest.approx(2110.0)
    expected = (
        cost_of(Usage(input_tokens=900, output_tokens=40), "claude-haiku-4-5")
        + cost_of(Usage(input_tokens=1500, output_tokens=220), "claude-sonnet-5")
    )
    assert meter.total_cost == pytest.approx(expected)


def test_meter_record_returns_a_priced_row():
    meter = Meter()
    rec = meter.record("plan", "claude-haiku-4-5", Usage(input_tokens=100, output_tokens=10), latency_ms=42.0)
    assert isinstance(rec, CallRecord)
    assert rec.label == "plan" and rec.model == "claude-haiku-4-5"
    assert rec.cost_usd == pytest.approx((100 * 1.0 + 10 * 5.0) / MTOK)


def test_meter_report_shows_each_call_and_the_total():
    meter = Meter()
    meter.record("plan", "claude-haiku-4-5", Usage(input_tokens=900, output_tokens=40), latency_ms=310.0)
    report = meter.report()
    assert "plan" in report and "claude-haiku-4-5" in report
    assert "TOTAL" in report


# --- measure ---------------------------------------------------------------

def test_measure_reports_elapsed_wall_time():
    with measure() as sw:
        time.sleep(0.02)
    # a real timer over a 20ms sleep: at least ~15ms (leave slack for scheduling), and clearly positive
    assert sw.ms >= 15.0
