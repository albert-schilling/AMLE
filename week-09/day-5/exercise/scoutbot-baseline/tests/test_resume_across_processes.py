"""Day 2's headline claim, tested the only way it can honestly be tested: with separate processes.

Everything in `test_graph.py` runs in one interpreter, so at best it proves that a second
*connection* can resume a run. The claim on the slides is stronger than that, and it is the reason
the topic exists: a run survives the process dying. That needs `subprocess`.

Day 3 makes the chain one process longer, and the extra link is the point of the day. The run is
killed, a second process recovers it and arrives at the pause, and a *third* process is the human
answering. Three interpreters, three fresh mocks, and the model is called exactly once across all
of them.

Day 4 adds the other half of the same claim. Progress surviving a restart is worth little if the
run's *effects* do not: a fourth process that tries to send the same reply again has to be refused,
and the only thing that can refuse it is a record on disk. `test_the_ledger_refuses_a_duplicate_from
_a_completely_separate_process` is that case, and it is the strongest form of the day's guarantee
available - no shared memory, no shared graph, nothing but a file.

The child processes patch `scoutbot.core._client` themselves, so this stays offline like every
other test. Their model-call counts are the assertions that matter.

One small piece of plumbing worth explaining rather than hiding: the children print their JSON
result on the **last** line of stdout, and the parent reads only that line. As of today `send_reply`
prints the email it sends, so stdout is no longer exclusively a data channel - which is a small,
real example of a side effect making a program harder to test.
"""
import json
import subprocess
import sys

# Run inside a child interpreter, once per phase. Kept as source text rather than a helper module
# so that everything the child does is visible in one place.
PROGRAM = '''
import json, sys
from types import SimpleNamespace
from unittest.mock import patch

from langgraph.types import Command

import numpy as np

import scoutbot.graph as graph_module
from scoutbot.graph import (
    build_ticket_graph, initial_state, sqlite_checkpointer, thread_config,
)
from scoutbot.knowledge import Chunk, KnowledgeBase
from scoutbot.notify import Ledger

db_path, phase, durability = sys.argv[1], sys.argv[2], sys.argv[3]
TRIAGE = {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}
RESPONSE = SimpleNamespace(
    content=[SimpleNamespace(type="tool_use", name="triage_ticket", input=TRIAGE)]
)

# Inject an offline knowledge base, exactly as the in-process tests do: Day 2 retrieves on every
# ticket, and a child process must not download a real embedding model to run this durability test.
# "I was charged twice." matches the billing axis, so it retrieves the billing passage at score 1.0.
_AXES = ["refund", "shipping", "warranty", "billing"]
_AXIS_WORDS = {
    "refund": ("refund", "refunds"), "shipping": ("shipping", "ship"),
    "warranty": ("warranty", "defect"), "billing": ("billing", "charged", "charge", "twice"),
}


def keyword_embedder(texts):
    out = []
    for t in texts:
        low = t.lower()
        v = np.array([1.0 if any(w in low for w in _AXIS_WORDS[a]) else 0.0 for a in _AXES],
                     dtype=np.float32)
        out.append(v if v.any() else np.ones(len(_AXES), dtype=np.float32))
    return out


def fake_kb():
    kb = KnowledgeBase(keyword_embedder)
    kb.index([
        Chunk("refunds", 0, "refunds are issued within five business days"),
        Chunk("shipping", 0, "shipping is free over fifty euros"),
        Chunk("warranty", 0, "the warranty covers manufacturing defects"),
        Chunk("billing", 0, "a duplicate charge is reversed within two days"),
    ])
    return kb


graph_module._PROCESS_KB = fake_kb()


def echo_formulate(ticket_text, tried_queries=(), weak_passages=""):
    # Day 3 runs formulate_query on every ticket, and the real one is a model call. Echo the ticket so
    # retrieval searches what the billing axis matches, keeping the child fully offline.
    return ticket_text


graph_module.formulate_query = echo_formulate


def route_iterative(ticket_text):
    # Day 4 routes every ticket through a model call; force the full loop so this durability test runs
    # the same path Day 3 did, without spending a real classify call.
    return "iterative"


graph_module.classify_query = route_iterative


class FakeStream:
    """`client.messages.stream(...)`: a context manager exposing `.text_stream`."""
    def __enter__(self):
        return SimpleNamespace(text_stream=iter(["Looking ", "into it."]))
    def __exit__(self, *exc_info):
        return False


def die_hard(state):
    """No exception, no cleanup: the box simply stops existing."""
    import os
    os._exit(9)


with patch("scoutbot.core._client") as mock_client:
    mock_client.return_value.messages.create.return_value = RESPONSE
    mock_client.return_value.messages.stream.return_value = FakeStream()
    config = thread_config("T-4471")

    # The ledger lives in the same file as the checkpoints, so one path is the whole record of a
    # run: where it got to, and what it has already done to the outside world.
    ledger = Ledger.at(db_path)

    if phase == "crash":
        graph_module.escalate_node = die_hard
        graph = build_ticket_graph(sqlite_checkpointer(db_path), ledger=ledger)
        graph.invoke(
            initial_state("I was charged twice.", "1001", "T-4471"),
            config,
            durability=durability,
        )
    elif phase == "send_again":
        # A brand new run of the same ticket, on its own thread, in its own process, approved all
        # over again by the same person. Nothing about this run knows the earlier one happened -
        # except the ledger. This is the shape of the real accident: a ticket re-opened, re-queued,
        # or simply run twice by a retry somewhere above the graph entirely.
        graph = build_ticket_graph(sqlite_checkpointer(db_path), ledger=ledger)
        again = thread_config("T-4471-again")
        graph.invoke(
            initial_state("I was charged twice.", "1001", "T-4471"), again, durability=durability
        )
        final = graph.invoke(
            Command(resume={"approved": True, "by": "priya", "role": "support_lead"}),
            again,
            durability=durability,
        )
        print(json.dumps({
            "notes": final.get("notes", []),
            "ledger_rows": len(ledger.entries()),
        }))
    else:
        graph = build_ticket_graph(sqlite_checkpointer(db_path), ledger=ledger)
        snapshot = graph.get_state(config)
        if not snapshot.next:
            # Nothing pending means there is nothing to resume, so don't pretend otherwise.
            final = {}
        elif phase == "resume":
            # `None` continues an unfinished run. It is not an answer to anything.
            final = graph.invoke(None, config, durability=durability)
        else:
            # A person, in a process of their own, days later as far as the run knows.
            final = graph.invoke(
                Command(resume={"approved": True, "by": "priya", "role": "support_lead"}),
                config,
                durability=durability,
            )
        print(json.dumps({
            "pending_at_startup": list(snapshot.next),
            "paused_again": "__interrupt__" in final,
            "notes": final.get("notes", []),
            "resolution": final.get("resolution", {}),
            "draft_reply": final.get("draft_reply", ""),
            "ledger_rows": len(ledger.entries()),
            "model_calls_in_this_process": (
                mock_client.return_value.messages.create.call_count
                + mock_client.return_value.messages.stream.call_count
            ),
        }))
'''


def _run_phase(db_path, phase, durability="sync"):
    return subprocess.run(
        [sys.executable, "-c", PROGRAM, str(db_path), phase, durability],
        capture_output=True,
        text=True,
    )


def _result(completed):
    """The child's JSON, which is the last line of its stdout.

    Anything the run printed on its way - including the email `send_reply` sends - comes first.
    """
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_a_run_survives_the_process_being_killed(tmp_path):
    db_path = tmp_path / "checkpoints.db"

    crashed = _run_phase(db_path, "crash")
    assert crashed.returncode == 9, crashed.stderr

    result = _result(_run_phase(db_path, "resume"))

    # The second process knew, on startup and from disk alone, which node still owed work.
    assert result["pending_at_startup"] == ["escalate"]
    # And it got as far as the pause, which is exactly as far as a run can get on its own.
    assert result["paused_again"] is True
    assert result["resolution"] == {}
    assert result["draft_reply"] == "Looking into it."
    # The whole economic argument for checkpointing, in one assertion: the process that recovered
    # the run never called the model.
    assert result["model_calls_in_this_process"] == 0


def test_a_third_process_answers_the_question_and_the_run_finishes(tmp_path):
    """The day's claim, end to end, across three interpreters.

    Nothing is shared but a `thread_id` and a file. The answer given here is the return value of an
    `interrupt()` call made in a process that no longer exists.
    """
    db_path = tmp_path / "checkpoints.db"

    assert _run_phase(db_path, "crash").returncode == 9
    assert _run_phase(db_path, "resume").returncode == 0

    result = _result(_run_phase(db_path, "answer"))

    assert result["pending_at_startup"] == ["escalate"]
    assert result["paused_again"] is False
    assert result["resolution"]["path"] == "escalated"
    assert result["resolution"]["approved"] is True
    assert result["resolution"]["reviewed_by"] == "priya"
    assert result["notes"] == [
        "looked up 1001: found",
        "triaged as billing/high",
        "routed to iterative retrieval",
        "search query: 'I was charged twice.'",
        "retrieved 3 passages (best [billing] at 1.00)",
        "critique: retrieval is sufficient (best 1.00)",
        "drafted a grounded reply",
        "policy: needs support_lead (triaged high priority, so a person should see it)",
        "priya approved the draft",
        "reply sent to the customer (ledger key T-4471:send_reply)",
    ]
    assert result["model_calls_in_this_process"] == 0
    # The reply went out in this process, and the record of it went to disk in the same breath.
    assert result["ledger_rows"] == 1


def test_the_ledger_refuses_a_duplicate_from_a_completely_separate_process(tmp_path):
    """Today's guarantee in its strongest available form: four processes, one email.

    The first three crash, recover and approve, and the third sends the reply. The fourth starts the
    same ticket over from scratch on a different `thread_id`, so there is no checkpoint for it to
    resume and nothing in memory to consult. It runs every node, reaches `send_reply`, finds the row
    its predecessor wrote, and declines.

    Worth being precise about what this proves and what it does not. It proves the record outlives
    the process that wrote it, which is what makes the guarantee real rather than per-process. It
    does not prove exactly-once delivery: a process killed between the send and the `INSERT` leaves
    no row, and the next attempt sends again. That window is named in `notify.py` and is the honest
    limit of the technique.
    """
    db_path = tmp_path / "checkpoints.db"

    assert _run_phase(db_path, "crash").returncode == 9
    assert _run_phase(db_path, "resume").returncode == 0
    assert _result(_run_phase(db_path, "answer"))["ledger_rows"] == 1

    result = _result(_run_phase(db_path, "send_again"))

    assert result["notes"][-1] == "reply already sent for T-4471, so this attempt sent nothing"
    assert result["ledger_rows"] == 1


def test_durability_exit_saves_nothing_when_the_process_is_killed(tmp_path):
    """Why the durability mode is worth choosing deliberately rather than leaving alone.

    `"exit"` persists only when the graph finishes, so a killed run leaves nothing to come back to
    and Saturday starts from scratch. The library's actual default, `"async"`, sits between this and
    `"sync"`: it writes a step's checkpoint while the next step runs, so a kill sometimes wins the
    race and sometimes does not. That middle case is deliberately not asserted here, because a test
    of a race would be as unreliable as the race itself. `"exit"` makes the same point with a
    guarantee instead: the knob is real, and the default is not the safest setting.

    Note that a *pause* needs none of this. It ends the run cleanly, so the default durability
    commits it; `run_events.py` passes no durability argument at all. `"sync"` is about surviving a
    kill, not about surviving a wait.
    """
    db_path = tmp_path / "checkpoints.db"

    crashed = _run_phase(db_path, "crash", durability="exit")
    assert crashed.returncode == 9, crashed.stderr

    result = _result(_run_phase(db_path, "resume"))

    assert result["pending_at_startup"] == []
    assert result["notes"] == []
