"""Day 2's headline claim, tested the only way it can honestly be tested: with separate processes.

Everything in `test_graph.py` runs in one interpreter, so at best it proves that a second
*connection* can resume a run. The claim on the slides is stronger than that, and it is the reason
the topic exists: a run survives the process dying. That needs `subprocess`.

Day 3 makes the chain one process longer, and the extra link is the point of the day. The run is
killed, a second process recovers it and arrives at the pause, and a *third* process is the human
answering. Three interpreters, three fresh mocks, and the model is called exactly once across all
of them.

The child processes patch `scoutbot.core._client` themselves, so this stays offline like every
other test. Their model-call counts are the assertions that matter.
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

import scoutbot.graph as graph_module
from scoutbot.graph import (
    build_ticket_graph, initial_state, sqlite_checkpointer, thread_config,
)

db_path, phase, durability = sys.argv[1], sys.argv[2], sys.argv[3]
TRIAGE = {"category": "billing", "priority": "high", "suggested_owner": "billing-team"}
RESPONSE = SimpleNamespace(
    content=[SimpleNamespace(type="tool_use", name="triage_ticket", input=TRIAGE)]
)


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

    if phase == "crash":
        graph_module.escalate_node = die_hard
        graph = build_ticket_graph(sqlite_checkpointer(db_path))
        graph.invoke(
            initial_state("I was charged twice.", "1001", "T-4471"),
            config,
            durability=durability,
        )
    else:
        graph = build_ticket_graph(sqlite_checkpointer(db_path))
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
                Command(resume={"approved": True, "by": "priya"}), config, durability=durability
            )
        print(json.dumps({
            "pending_at_startup": list(snapshot.next),
            "paused_again": "__interrupt__" in final,
            "notes": final.get("notes", []),
            "resolution": final.get("resolution", {}),
            "draft_reply": final.get("draft_reply", ""),
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


def test_a_run_survives_the_process_being_killed(tmp_path):
    db_path = tmp_path / "checkpoints.db"

    crashed = _run_phase(db_path, "crash")
    assert crashed.returncode == 9, crashed.stderr

    resumed = _run_phase(db_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads(resumed.stdout)

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

    answered = _run_phase(db_path, "answer")
    assert answered.returncode == 0, answered.stderr
    result = json.loads(answered.stdout)

    assert result["pending_at_startup"] == ["escalate"]
    assert result["paused_again"] is False
    assert result["resolution"]["path"] == "escalated"
    assert result["resolution"]["approved"] is True
    assert result["resolution"]["reviewed_by"] == "priya"
    assert result["notes"] == [
        "looked up 1001: found",
        "triaged as billing/high",
        "drafted a reply",
        "human approved the draft: priya",
    ]
    assert result["model_calls_in_this_process"] == 0


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

    resumed = _run_phase(db_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads(resumed.stdout)

    assert result["pending_at_startup"] == []
    assert result["notes"] == []
