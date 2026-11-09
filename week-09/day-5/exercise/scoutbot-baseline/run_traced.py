"""The day in one file: run the graph traced, watch the spans, then read the run back.

Two commands:

    python run_traced.py            # a clean run, traced end to end, then read back from the file
    python run_traced.py --paused   # a run that pauses in one "process" and resumes in another

The first command runs a small, auto-approved ticket all the way through with tracing switched on.
Real OpenTelemetry spans print to the terminal as each node finishes (that is the SDK's
`ConsoleSpanExporter`, not our code), and the same spans are appended to `scoutbot_spans.jsonl`. Then
the run is *read back*: `read_spans()` reassembles the trace from the file - one trace, one span per
node, real per-node timing - and `get_state_history()` walks the checkpointer's own timeline of the
run. Neither re-runs the graph. That is the whole point of a trace: a question answered after the run
is over.

The second command is the honest one. A nine-hundred-euro refund pauses for a billing manager, and
then a *separate* run resumes it. Because a resume is a new process with an empty tracing context, the
paused half and the resumed half are **two different traces** - OpenTelemetry has nothing that spans
the gap. What ties them into one story is the id every span carries: `scoutbot.run_id`, set from the
ticket id, the very same `thread_id` the ledger keyed on yesterday. The reader groups the file by that
id and shows both traces under it, and `get_state_history()` - which is durable, so it does cross the
gap - shows the run as one continuous timeline.

The two halves here run in one process for a one-command demo. In production they are two processes on
two days; the tracing consequence is identical, which is exactly why the id, not the trace, is what
finds a run again. To see two genuine OS processes, `run_resume.py` from Tuesday still does that.

Nothing about the graph changed to make this work. `build_ticket_graph(tracer=...)` wraps each node in
a span; `build_ticket_graph()` with no tracer is byte-for-byte Thursday's graph, which is why the old
tests never noticed today happened.
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command

from scoutbot import (
    Ledger,
    build_ticket_graph,
    build_tracer,
    initial_state,
    read_spans,
    reset_flaky_counter,
    run_span,
    sqlite_checkpointer,
    thread_config,
)

load_dotenv()

DB_PATH = Path(__file__).parent / "checkpoints.db"
SPANS_PATH = Path(__file__).parent / "scoutbot_spans.jsonl"

# A small, benign ticket for the clean run: zero euros, a plain account question, on an account with
# no refund history (customer 1002). It stays under every threshold, so the policy auto-approves and
# the run finishes - which is what makes it a complete, single trace to read back.
CLEAN_ID = "T-5500"
CLEAN_TEXT = "Could you confirm which email address my invoices are being sent to?"
CLEAN_CUSTOMER = "1002"
CLEAN_AMOUNT = 0.0

# The refund ticket the week has been carrying, for the paused case: large enough that the policy
# demands a billing manager, so the run stops and a second run has to finish it.
PAUSE_ID = "T-4471"
PAUSE_TEXT = "I was charged twice for my annual plan and I want one of the charges refunded today."
PAUSE_CUSTOMER = "1001"
PAUSE_AMOUNT = 900.0
DANA = {"by": "dana", "role": "billing_manager"}


def _reset() -> None:
    """Start every demo from nothing: no checkpoints, no ledger, no spans from a previous run."""
    for path in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm"), SPANS_PATH):
        path.unlink(missing_ok=True)
    reset_flaky_counter()


def _graph(tracer):
    """Today's graph: Thursday's build plus a tracer, on a file-backed checkpointer and ledger."""
    return build_ticket_graph(
        checkpointer=sqlite_checkpointer(DB_PATH),
        ledger=Ledger.at(DB_PATH),
        tracer=tracer,
    )


def _print_notes(node_name: str, update: dict) -> None:
    for note in update.get("notes", []):
        print(f"  {node_name}: {note}")


def _drive(graph, payload, config) -> None:
    """Stream a run to completion (or to a pause), printing each node's notes as it lands."""
    for mode, chunk in graph.stream(payload, config, stream_mode=["updates", "custom"]):
        if mode == "custom":
            continue  # the draft still streams here; today's lens is the spans, not the tokens
        for node_name, update in chunk.items():
            if node_name == "__interrupt__":
                payload = update[0].value
                print(f"\n  PAUSED, waiting for: {payload['approver_required']}")
                print(f"  because: {payload['why']}\n")
                continue
            _print_notes(node_name, update)


def _read_trace_back(run_id: str) -> None:
    """The 'query it, don't re-run it' half: reassemble the run from the saved span file."""
    records = [r for r in read_spans(SPANS_PATH) if r.get("run_id") == run_id]
    node_spans = [r for r in records if (r.get("node") is not None)]
    trace_ids = sorted({r["trace_id"] for r in records})

    print(f"\n=== read back from {SPANS_PATH.name}: run_id={run_id} ===")
    print(f"  {len(records)} spans across {len(trace_ids)} trace(s)")
    for trace_id in trace_ids:
        in_trace = [r for r in records if r["trace_id"] == trace_id]
        print(f"\n  trace {trace_id[:16]}...  ({len(in_trace)} spans)")
        for r in sorted(in_trace, key=lambda r: r["duration_ms"], reverse=True):
            label = r["node"] or r["name"]
            print(f"      {label:18s} {r['duration_ms']:8.2f} ms   {r['status']}")
    if node_spans:
        slowest = max(node_spans, key=lambda r: r["duration_ms"])
        print(f"\n  slowest node this run: {slowest['node']} "
              f"({slowest['duration_ms']:.2f} ms) - answered without re-running the graph.")
    if len(trace_ids) > 1:
        print(f"\n  NOTE: {len(trace_ids)} traces for one run. A resume is a new process, so the")
        print("  trace does not span the pause. The shared run_id above is what ties them together.")


def _read_history(graph, config) -> None:
    """The durable half: the checkpointer's own timeline, which needs no tracing and crosses a pause."""
    history = list(graph.get_state_history(config))
    print(f"\n=== get_state_history(): {len(history)} checkpoints (newest first) ===")
    for snap in history:
        step = snap.metadata.get("step")
        nxt = snap.next or "()"
        print(f"  step {step:>2}  next={nxt}")
    newest = history[0]
    if newest.next:
        print(f"  newest still owes: {newest.next} - this run has not finished.")
    else:
        print("  newest .next is empty: this run finished. The whole path above is durable,")
        print("  readable from a fresh process days later, with no span and no re-run.")


def clean_run() -> None:
    """A traced run that finishes, then read back two ways."""
    _reset()
    tracer = build_tracer(to_console=True, span_path=SPANS_PATH)
    graph = _graph(tracer)
    config = thread_config(CLEAN_ID)

    print(f"=== {CLEAN_ID}: traced run (spans print below as each node ends) ===\n")
    # The root span. Without it, each node span would be its own separate trace; with it, they are
    # one trace for the run. The run_id stamped here is the thread key, so the trace is findable later.
    with run_span(tracer, run_id=CLEAN_ID):
        _drive(
            graph,
            initial_state(CLEAN_TEXT, CLEAN_CUSTOMER, CLEAN_ID, refund_amount=CLEAN_AMOUNT),
            config,
        )

    _read_trace_back(CLEAN_ID)
    _read_history(graph, config)


def paused_run() -> None:
    """A run that pauses under one root span and resumes under another: two traces, one id."""
    _reset()
    config = thread_config(PAUSE_ID)

    print(f"=== {PAUSE_ID}: process 1 - run until the billing manager is needed ===\n")
    tracer_1 = build_tracer(to_console=False, span_path=SPANS_PATH)
    graph_1 = _graph(tracer_1)
    with run_span(tracer_1, run_id=PAUSE_ID):
        _drive(
            graph_1,
            initial_state(PAUSE_TEXT, PAUSE_CUSTOMER, PAUSE_ID, refund_amount=PAUSE_AMOUNT),
            config,
        )

    print(f"=== {PAUSE_ID}: process 2 - a fresh tracer resumes it (Dana approves) ===\n")
    # A new tracer from a new provider: this stands in for a second process, whose tracing context
    # starts empty. That empty context is the whole reason the resume becomes a second trace.
    tracer_2 = build_tracer(to_console=False, span_path=SPANS_PATH)
    graph_2 = _graph(tracer_2)
    with run_span(tracer_2, run_id=PAUSE_ID):
        _drive(graph_2, Command(resume={"approved": True, **DANA}), config)

    final = graph_2.get_state(config)
    print(f"  resolution: {json.dumps(final.values['resolution'])}")

    _read_trace_back(PAUSE_ID)
    _read_history(graph_2, config)


def main() -> None:
    if "--paused" in set(sys.argv[1:]):
        paused_run()
    else:
        clean_run()


if __name__ == "__main__":
    main()
