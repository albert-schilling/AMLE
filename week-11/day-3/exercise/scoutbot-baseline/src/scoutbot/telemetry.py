"""Structured logging for ScoutBot's loop, added on Day 5.

The flipped material and live lesson's own point: this needs no new dependency and no
tracing library, just the two things already in the standard library - `json` and
`open()`. One JSON line per loop step, appended to a plain file (JSON Lines / JSONL), with
exactly the fields the flipped material's field-list challenge asked for, plus timing.

This is deliberately just enough to make the loop's *existing* trace queryable after the
fact - not a full observability/tracing library. See `main.py`'s `_summarize_log()` for a
worked example of answering a real question from the saved file, without re-running
anything.
"""
import json
from pathlib import Path
from typing import Optional

DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "scoutbot_log.jsonl"


def log_step(ticket_id: str, step_number: int, step, duration_ms: float, log_path: Optional[Path] = None) -> None:
    """Append one JSON line recording a single loop step. Same shape whether `step` came
    from a client tool or a server tool - the logger doesn't branch on tool type, only on
    whether a step happened at all (see `loop.run_agent_loop`)."""
    path = Path(log_path) if log_path else DEFAULT_LOG_PATH
    record = {
        "ticket_id": ticket_id,
        "step": step_number,
        "tool": step.action,
        "duration_ms": round(duration_ms, 1),
        "errored": _step_errored(step),
    }
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _step_errored(step) -> bool:
    """A step "errored" if its observation is a client tool's `{"error": ...}` dict, or a
    server tool's non-zero/errored result (see `loop._summarize_server_tool_result`)."""
    obs = step.observation
    if not isinstance(obs, dict):
        return False
    if "error" in obs:
        return True
    if obs.get("return_code") not in (None, 0):
        return True
    return False


def read_log(log_path: Optional[Path] = None) -> list:
    """Read every saved record back out of the log file, oldest first - the "query it,
    don't re-run it" half of today's lesson. Returns `[]` if the file doesn't exist yet
    (nothing has been logged), rather than raising."""
    path = Path(log_path) if log_path else DEFAULT_LOG_PATH
    if not path.exists():
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
