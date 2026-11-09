"""The day's headline claim, tested the only way it can honestly be tested: with two processes.

Everything in `test_graph.py` runs in one interpreter, so at best it proves that a second
*connection* can resume a run. The claim on the slides is stronger than that, and it is the reason
the topic exists: a run survives the process dying. That needs `subprocess`.

The child processes patch `scoutbot.core._client` themselves, so this stays offline like every
other test. The second child's model-call count is the assertion that matters: it is a fresh
interpreter with a fresh mock, and it finishes the run having never called the model at all.
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

import scoutbot.graph as graph_module
from scoutbot.graph import (
    build_ticket_graph, initial_state, sqlite_checkpointer, thread_config,
)

db_path, phase, durability = sys.argv[1], sys.argv[2], sys.argv[3]
TRIAGE = {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}
RESPONSE = SimpleNamespace(
    content=[SimpleNamespace(type="tool_use", name="triage_ticket", input=TRIAGE)]
)


def die_hard(state):
    """No exception, no cleanup: the box simply stops existing."""
    import os
    os._exit(9)


with patch("scoutbot.core._client") as mock_client:
    mock_client.return_value.messages.create.return_value = RESPONSE
    graph = None
    if phase == "crash":
        graph_module.escalate_node = die_hard
        graph = build_ticket_graph(sqlite_checkpointer(db_path))
        graph.invoke(
            initial_state("I was charged twice.", "1001", "T-4471"),
            thread_config("T-4471"),
            durability=durability,
        )
    else:
        graph = build_ticket_graph(sqlite_checkpointer(db_path))
        snapshot = graph.get_state(thread_config("T-4471"))
        # Nothing pending means there is nothing to resume, so don't pretend otherwise.
        final = graph.invoke(None, thread_config("T-4471")) if snapshot.next else {}
        print(json.dumps({
            "pending_at_startup": list(snapshot.next),
            "notes": final.get("notes", []),
            "resolution": final.get("resolution", {}),
            "model_calls_in_this_process": mock_client.return_value.messages.create.call_count,
        }))
'''


def _run_phase(db_path, phase, durability="sync"):
    return subprocess.run(
        [sys.executable, "-c", PROGRAM, str(db_path), phase, durability],
        capture_output=True,
        text=True,
    )


def test_a_run_survives_the_process_being_killed(tmp_path):
    db_path = tmp_path / "checkpoints.db"

    crashed = _run_phase(db_path, "crash")
    assert crashed.returncode == 9, crashed.stderr

    resumed = _run_phase(db_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads(resumed.stdout)

    # The second process knew, on startup and from disk alone, which node still owed work.
    assert result["pending_at_startup"] == ["escalate"]
    assert result["resolution"]["path"] == "escalated"
    assert result["notes"] == [
        "looked up 1001: found",
        "triaged as billing/high",
        "escalated: high priority, needs a human",
    ]
    # The whole economic argument for checkpointing, in one assertion: the process that finished
    # the run never called the model.
    assert result["model_calls_in_this_process"] == 0


def test_durability_exit_saves_nothing_when_the_process_is_killed(tmp_path):
    """Why the durability mode is worth choosing deliberately rather than leaving alone.

    `"exit"` persists only when the graph finishes, so a killed run leaves nothing to come back to
    and Saturday starts from scratch. The library's actual default, `"async"`, sits between this and
    `"sync"`: it writes a step's checkpoint while the next step runs, so a kill sometimes wins the
    race and sometimes does not. That middle case is deliberately not asserted here, because a test
    of a race would be as unreliable as the race itself. `"exit"` makes the same point with a
    guarantee instead: the knob is real, and the default is not the safest setting.
    """
    db_path = tmp_path / "checkpoints.db"

    crashed = _run_phase(db_path, "crash", durability="exit")
    assert crashed.returncode == 9, crashed.stderr

    resumed = _run_phase(db_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads(resumed.stdout)

    assert result["pending_at_startup"] == []
    assert result["notes"] == []
