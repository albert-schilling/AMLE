"""OpenTelemetry tracing for ScoutBot's graph, added on Day 5, and run entirely offline.

Week 7 Day 5 made the *loop's* trace queryable with a hand-rolled JSONL logger. That was the right
first step and it was deliberately not a tracing library. Today is the tracing library, applied to
the *graph*: each node execution becomes a **span** (a named, timed unit of work with a status), and
all the spans for one run are gathered under a single **trace**. That is what OpenTelemetry gives you
that a `notes` field and a pile of `print()`s do not - structure, timing, and a shape you can query
after the run is over.

**It runs with no account and no network.** OpenTelemetry is two things: an API for creating spans
and an SDK for deciding where they go. The SDK's exporters are just sinks. This module uses the
`ConsoleSpanExporter` that ships with the SDK, plus a tiny `JsonlSpanExporter` written here, so the
trace lands on the terminal and in a local file. Pointing the same spans at a hosted backend (Jaeger,
Tempo, Honeycomb, a LangSmith OTLP endpoint) is one exporter swap and is the only thing this day owes
a vendor. That is why "no LangSmith account needed", true all week, is still true today.

Four facts worth having in front of you before editing this file, all from a spike against
langgraph 1.2.10 + opentelemetry-sdk 1.44 rather than from a blog post, and the first one reverses
the trap the blog posts warn about:

- **For this graph, the ambient span context propagates across nodes on its own.** The widely
  documented "orphaned span" problem - each node starting its own root trace because OpenTelemetry's
  active span lives in a `contextvars.ContextVar` that a fresh call frame does not inherit - does not
  reproduce here. LangGraph runs each sync node via `context.run(...)` on the calling thread, so a
  child span opened inside a node parents correctly to the run's root span across the linear chain,
  across the conditional edge, and even across a retried node's re-runs. No context-carried-in-state
  trick is needed, which is why `TicketState` gains no field today and Day 4's tests are untouched.
- **One trace per run needs a root span opened around the run.** Verified: without a root span, each
  node's span becomes its own separate trace (one node, one trace). So `run_span()` below opens the
  root, and everything inside it is one trace. The node wrapper alone is not enough.
- **A trace does not survive a pause and resume.** A resume is a new process: its context is empty
  and the first run's spans were flushed when that process ended. So a paused-then-resumed run has
  *more than one* trace, and nothing in OpenTelemetry stitches them together. What does is a **stable
  id stamped on every span** - here `scoutbot.run_id`, set from the ticket id, which is the very same
  `thread_id` Thursday's ledger keyed on. The trace shows a run while it happens; the id is how you
  find all of a run's pieces afterwards. This is the honest limit, and it is the day's second topic.
- **Span duration is real per-node wall time.** Unlike Week 7's loop logger, where every step in one
  API turn had to share a single turn-level duration, each span times exactly its own node, so a slow
  node is visibly slow.

Nothing here is on by default. `graph.py` compiles an un-traced graph unless you ask for a traced one,
exactly as Week 7 Day 5's logging was opt-in behind `log_path=None`.
"""
import inspect
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from langgraph.errors import GraphBubbleUp
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Status, StatusCode, Tracer

DEFAULT_SPAN_PATH = Path(__file__).resolve().parents[2] / "scoutbot_spans.jsonl"

SERVICE_NAME = "scoutbot"
RUN_SPAN_NAME = "scoutbot.run"

# Attribute keys, named once so the exporter and the reader cannot drift apart.
ATTR_NODE = "scoutbot.node"
ATTR_RUN_ID = "scoutbot.run_id"


class JsonlSpanExporter(SpanExporter):
    """Write one JSON line per finished span to a local file. The 'read it back' sink.

    This is the graph-level sibling of Week 7 Day 5's `telemetry.log_step`: an append-only file of
    flat records, no rotation and no library, just enough that `read_spans()` can answer a question
    about a past run without re-running it. Each record carries the ids that make a span placeable in
    its trace (`trace_id`, `span_id`, `parent_id`), so the file alone can be reassembled into the
    run's shape.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else DEFAULT_SPAN_PATH

    def export(self, spans) -> SpanExportResult:
        with open(self.path, "a") as f:
            for span in spans:
                f.write(json.dumps(_span_to_record(span)) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:  # pragma: no cover - nothing to release for a plain file
        pass


def _span_to_record(span) -> dict:
    """The flat, JSON-serialisable shape of one finished span.

    `start_time`/`end_time` are integer nanoseconds since the epoch; the difference is the span's own
    duration, which is the per-node timing the whole exercise is after.
    """
    ctx = span.get_span_context()
    duration_ms = (span.end_time - span.start_time) / 1e6
    attrs = dict(span.attributes or {})
    return {
        "name": span.name,
        "trace_id": f"{ctx.trace_id:032x}",
        "span_id": f"{ctx.span_id:016x}",
        "parent_id": f"{span.parent.span_id:016x}" if span.parent else None,
        "run_id": attrs.get(ATTR_RUN_ID),
        "node": attrs.get(ATTR_NODE),
        "status": span.status.status_code.name,
        "duration_ms": round(duration_ms, 2),
    }


def build_tracer(
    service: str = SERVICE_NAME,
    to_console: bool = True,
    span_path: Optional[Path] = None,
    extra_exporter: Optional[SpanExporter] = None,
) -> Tracer:
    """A tracer whose spans go to the console and/or a local JSONL file, and nowhere else.

    Deliberately does **not** call `trace.set_tracer_provider()`. That global is process-wide and can
    only be set once, so setting it would make two runs in one process (or two tests) fight over it.
    A local `TracerProvider` avoids that entirely: span *nesting* is decided by the OpenTelemetry
    context, which is global, so a tracer from a local provider still parents child spans correctly
    (verified). Each exporter is wrapped in a `SimpleSpanProcessor`, which exports every span the
    moment it ends - the right choice for a teaching tool, where seeing the span immediately matters
    more than the batching a production setup would use.

    `extra_exporter` is the seam a test uses to collect spans in memory, and the seam a real system
    would use to add an OTLP exporter pointing at a backend. That swap is the whole "point it
    somewhere real" story, and it is one argument.
    """
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    if span_path is not None:
        provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(span_path)))
    if to_console:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    if extra_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(extra_exporter))
    return provider.get_tracer(service)


def trace_node(fn: Callable, name: str, tracer: Tracer) -> Callable:
    """Wrap one node so entering it opens a child span, without changing the node itself.

    The wrapper is signature-preserving on purpose. LangGraph decides what to inject into a node
    (`state`, and by-name extras like `writer`) by inspecting its signature, so the wrapper copies the
    wrapped callable's signature onto itself. Without that, a wrapper declared `(*args, **kwargs)`
    would hide the `writer` parameter and `draft_reply`'s streaming would silently stop. With it, the
    node keeps being an ordinary function that a test can still call with a hand-made dict - the
    property every day this fortnight has protected - and it simply also emits a span.

    The span records the node name and the run id (from `state["ticket_id"]`, the stable thread key),
    sets its status to ERROR and records the exception on the way out if the node raises, and OK
    otherwise. Re-raising matters: a node under a `RetryPolicy` must still fail so LangGraph retries
    it, and each retry is its own span, which is how the trace shows a node that ran three times.

    One exception is not an error: **a pause is not a failure.** `interrupt()` works by raising a
    `GraphInterrupt`, a subclass of LangGraph's `GraphBubbleUp` control-flow signal, which bubbles up
    to record the pause. Verified, and worth getting right: caught as a plain exception it would paint
    the paused node's span red, which reads as "escalate crashed" when the truth is "escalate stopped
    to ask a person". So it is caught first, tagged as an interrupt event with an OK status, and
    re-raised unchanged so the pause still happens.
    """

    def wrapper(*args, **kwargs):
        state = args[0] if args else kwargs.get("state")
        run_id = (state or {}).get("ticket_id") or "unknown"
        with tracer.start_as_current_span(f"node.{name}") as span:
            span.set_attribute(ATTR_NODE, name)
            span.set_attribute(ATTR_RUN_ID, run_id)
            try:
                result = fn(*args, **kwargs)
            except GraphBubbleUp:  # a pause (interrupt) is control flow, not a failure
                span.add_event("langgraph.interrupt")
                span.set_status(Status(StatusCode.OK))
                raise
            except Exception as exc:  # noqa: BLE001 - record, then re-raise unchanged
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            span.set_status(Status(StatusCode.OK))
            return result

    try:
        wrapper.__signature__ = inspect.signature(fn)
    except (ValueError, TypeError):  # pragma: no cover - builtins without signatures
        pass
    wrapper.__name__ = name
    return wrapper


@contextmanager
def run_span(tracer: Tracer, run_id: str):
    """Open the one root span a run's node spans hang from, keyed by the run id.

    Necessary, not decorative: without a root span active when the graph runs, each node's span is its
    own separate trace (verified). Wrapping the `invoke()`/`stream()` call in this is what makes the
    run one trace. The `run_id` is set here too, so even the root span carries the id that ties this
    trace to the same run's other traces - the ones a pause and resume will produce in other
    processes.
    """
    with tracer.start_as_current_span(RUN_SPAN_NAME) as span:
        span.set_attribute(ATTR_RUN_ID, run_id)
        yield span
        # Reached only on a clean exit; `start_as_current_span` sets ERROR itself if the body raised.
        span.set_status(Status(StatusCode.OK))


def read_spans(span_path: Optional[Path] = None) -> list:
    """Read every saved span record back, in the order it was written (oldest first).

    The 'query it, don't re-run it' half of the day, one layer up from Week 7's `read_log()`. Returns
    `[]` if the file does not exist yet rather than raising, so a caller can ask before anything has
    run. Records carry `trace_id`/`parent_id`, so a run that produced several traces (because it
    paused and resumed) can be grouped by `run_id` and each trace reassembled from the same file.
    """
    path = Path(span_path) if span_path else DEFAULT_SPAN_PATH
    if not path.exists():
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
