"""The tracing layer, tested with no model, no API key and no network.

Everything today's first topic promises is checked here against real OpenTelemetry spans - captured
in memory through the `extra_exporter` seam - and a real (if tiny) LangGraph run. No Anthropic call
happens in this file, which is the same discipline `test_policy.py` follows: the behaviour that can be
proven cheaply should be proven cheaply and exhaustively.

The mini-graph below stands in for ScoutBot's graph so the tests stay deterministic and offline. It
has the two node shapes that make wrapping tricky - a node LangGraph injects a `writer` into, and a
`functools.partial` node - so a passing suite here is evidence the same wrapper is safe on the real
graph, where those exact shapes are `draft_reply` and `send_reply`.
"""
import functools
import json
import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter, interrupt
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from scoutbot import build_tracer, read_spans, run_span, trace_node
from scoutbot.tracing import ATTR_NODE, ATTR_RUN_ID, RUN_SPAN_NAME


class _CollectingExporter(SpanExporter):
    """Keep finished spans in memory so a test can inspect parent/child links and attributes."""

    def __init__(self):
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def _tracer_and_sink(**kwargs):
    sink = _CollectingExporter()
    tracer = build_tracer(to_console=False, span_path=None, extra_exporter=sink, **kwargs)
    return tracer, sink


def _no_writer(_event):
    return None


class _State(TypedDict):
    ticket_id: str
    notes: Annotated[list, operator.add]


def _draft(state, writer: StreamWriter = _no_writer):
    """A node LangGraph injects `writer` into, exactly like the real `draft_reply`."""
    writer({"draft_chunk": "hi"})
    return {"notes": ["drafted"]}


def _send(state, ledger=None):
    return {"notes": [f"sent via {ledger}"]}


def _boom(state):
    raise ConnectionError("gateway dropped")


def _build(tracer, node_fn=None):
    b = StateGraph(_State)
    b.add_node("draft", trace_node(_draft, "draft", tracer))
    b.add_node("send", trace_node(functools.partial(_send, ledger="L"), "send", tracer))
    b.add_edge(START, "draft")
    b.add_edge("draft", "send")
    b.add_edge("send", END)
    return b.compile()


# --- the exporters, offline ---

def test_jsonl_exporter_round_trips_through_read_spans(tmp_path):
    span_file = tmp_path / "spans.jsonl"
    tracer = build_tracer(to_console=False, span_path=span_file)
    with run_span(tracer, run_id="T-1"):
        with tracer.start_as_current_span("node.solo") as span:
            span.set_attribute(ATTR_NODE, "solo")
            span.set_attribute(ATTR_RUN_ID, "T-1")

    records = read_spans(span_file)
    names = {r["name"] for r in records}
    assert RUN_SPAN_NAME in names and "node.solo" in names
    solo = next(r for r in records if r["name"] == "node.solo")
    assert solo["run_id"] == "T-1"
    assert solo["node"] == "solo"
    assert solo["duration_ms"] >= 0
    # Every record is placeable in its trace, which is what lets the file be reassembled later.
    assert solo["trace_id"] and solo["span_id"] and solo["parent_id"]


def test_read_spans_returns_empty_when_no_file(tmp_path):
    assert read_spans(tmp_path / "nothing.jsonl") == []


# --- the node wrapper ---

def test_wrapped_node_still_receives_injected_writer():
    tracer, _ = _tracer_and_sink()
    graph = _build(tracer)
    chunks = []
    for mode, chunk in graph.stream(
        {"ticket_id": "T-2", "notes": []}, stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            chunks.append(chunk)
    # If the wrapper hid the signature, LangGraph would not inject the writer and this would be empty.
    assert {"draft_chunk": "hi"} in chunks


def test_wrapped_partial_node_keeps_its_bound_arguments():
    tracer, _ = _tracer_and_sink()
    graph = _build(tracer)
    out = graph.invoke({"ticket_id": "T-3", "notes": []})
    assert out["notes"] == ["drafted", "sent via L"]


def test_node_span_carries_name_and_run_id_from_state():
    tracer, sink = _tracer_and_sink()
    graph = _build(tracer)
    graph.invoke({"ticket_id": "T-42", "notes": []})
    node_spans = [s for s in sink.spans if s.name.startswith("node.")]
    assert {s.name for s in node_spans} == {"node.draft", "node.send"}
    assert all(s.attributes[ATTR_RUN_ID] == "T-42" for s in node_spans)


def test_failing_node_span_is_error_and_exception_reraises():
    tracer, sink = _tracer_and_sink()
    b = StateGraph(_State)
    b.add_node("boom", trace_node(_boom, "boom", tracer))
    b.add_edge(START, "boom")
    b.add_edge("boom", END)
    graph = b.compile()

    with pytest.raises(ConnectionError):
        graph.invoke({"ticket_id": "T-err", "notes": []})

    boom = next(s for s in sink.spans if s.name == "node.boom")
    assert boom.status.status_code.name == "ERROR"
    # The wrapper must re-raise, or a node under a RetryPolicy would never be retried.


def test_a_pause_is_not_painted_as_an_error():
    tracer, sink = _tracer_and_sink()

    def _pauses(state):
        interrupt({"q": "approve?"})  # raises GraphInterrupt; the node never returns

    b = StateGraph(_State)
    b.add_node("gate", trace_node(_pauses, "gate", tracer))
    b.add_edge(START, "gate")
    b.add_edge("gate", END)
    graph = b.compile(checkpointer=InMemorySaver())

    graph.invoke({"ticket_id": "T-pause", "notes": []}, {"configurable": {"thread_id": "T-pause"}})

    gate = next(s for s in sink.spans if s.name == "node.gate")
    # A pause is control flow, not a crash: OK status, and an event that says what happened.
    assert gate.status.status_code.name != "ERROR"
    assert any(e.name == "langgraph.interrupt" for e in gate.events)


# --- one trace per run, and the honest limit ---

def test_run_span_makes_the_whole_run_one_trace():
    tracer, sink = _tracer_and_sink()
    graph = _build(tracer)
    with run_span(tracer, run_id="T-one"):
        graph.invoke({"ticket_id": "T-one", "notes": []})

    trace_ids = {s.context.trace_id for s in sink.spans}
    node_spans = [s for s in sink.spans if s.name.startswith("node.")]
    assert len(trace_ids) == 1
    assert all(s.parent is not None for s in node_spans)  # every node parents to the root


def test_without_a_root_span_each_node_is_its_own_trace():
    tracer, sink = _tracer_and_sink()
    graph = _build(tracer)
    graph.invoke({"ticket_id": "T-loose", "notes": []})  # no run_span wrapping it

    node_spans = [s for s in sink.spans if s.name.startswith("node.")]
    trace_ids = {s.context.trace_id for s in node_spans}
    # This is the verified reason run_span() exists: no root, no single trace.
    assert len(trace_ids) == len(node_spans) == 2


def test_two_runs_under_one_id_stay_correlated_across_traces(tmp_path):
    span_file = tmp_path / "spans.jsonl"
    # Two separate tracers stand in for two processes; both write the same run_id to the same file.
    for _ in range(2):
        tracer = build_tracer(to_console=False, span_path=span_file)
        graph = _build(tracer)
        with run_span(tracer, run_id="T-split"):
            graph.invoke({"ticket_id": "T-split", "notes": []})

    records = [r for r in read_spans(span_file) if r["run_id"] == "T-split"]
    trace_ids = {r["trace_id"] for r in records}
    assert len(trace_ids) == 2  # two traces, because a resume cannot share the first trace
    assert {r["run_id"] for r in records} == {"T-split"}  # but one id ties them together
