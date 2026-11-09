from scoutbot.loop import LoopStep
from scoutbot.telemetry import log_step, read_log


def test_read_log_returns_empty_list_for_a_missing_file(tmp_path):
    assert read_log(tmp_path / "nope.jsonl") == []


def test_log_step_appends_one_json_line_per_call(tmp_path):
    log_path = tmp_path / "log.jsonl"
    step_one = LoopStep(thought="Looking it up.", action="look_up_customer", observation={"found": True})
    step_two = LoopStep(thought="All done.")

    log_step("T-1", 1, step_one, duration_ms=123.456, log_path=log_path)
    log_step("T-1", 2, step_two, duration_ms=45.0, log_path=log_path)

    records = read_log(log_path)
    assert records == [
        {"ticket_id": "T-1", "step": 1, "tool": "look_up_customer", "duration_ms": 123.5, "errored": False},
        {"ticket_id": "T-1", "step": 2, "tool": None, "duration_ms": 45.0, "errored": False},
    ]


def test_log_step_flags_a_client_tool_error_observation(tmp_path):
    log_path = tmp_path / "log.jsonl"
    step = LoopStep(thought="Trying.", action="look_up_customer", observation={"error": "not found"})

    log_step("T-2", 1, step, duration_ms=10.0, log_path=log_path)

    assert read_log(log_path)[0]["errored"] is True


def test_log_step_flags_a_nonzero_return_code_as_errored(tmp_path):
    log_path = tmp_path / "log.jsonl"
    step = LoopStep(
        thought="Running.", action="bash_code_execution", observation={"stdout": "", "return_code": 1}
    )

    log_step("T-3", 1, step, duration_ms=10.0, log_path=log_path)

    assert read_log(log_path)[0]["errored"] is True


def test_log_step_appends_across_calls_rather_than_overwriting(tmp_path):
    log_path = tmp_path / "log.jsonl"
    step = LoopStep(thought="Done.")

    log_step("T-4", 1, step, duration_ms=1.0, log_path=log_path)
    log_step("T-5", 1, step, duration_ms=2.0, log_path=log_path)

    records = read_log(log_path)
    assert [r["ticket_id"] for r in records] == ["T-4", "T-5"]
