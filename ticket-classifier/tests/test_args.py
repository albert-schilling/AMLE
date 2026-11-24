from pathlib import Path

import pytest

from ticket_classifier.args import KbIndexArgs, ResumeArgs, RunArgs, parse_args


def test_run_with_tickets_file():
    assert parse_args(["run", "t.json"]) == RunArgs(tickets=Path("t.json"))


def test_run_without_tickets_file():
    assert parse_args(["run"]) == RunArgs(tickets=None)


@pytest.mark.parametrize(
    ("flag", "approved"), [("--approve", True), ("--decline", False)]
)
def test_resume_builds_the_answer(flag, approved):
    assert parse_args(["resume", "T-1", flag, "--note", "ok"]) == ResumeArgs(
        ticket_id="T-1", answer={"approved": approved, "note": "ok"}
    )


def test_kb_index():
    assert parse_args(["kb-index"]) == KbIndexArgs()


def test_resume_note_defaults_to_empty():
    assert parse_args(["resume", "T-1", "--approve"]).answer["note"] == ""


@pytest.mark.parametrize(
    "argv",
    [
        [],  # no subcommand
        ["resume", "T-1"],  # no decision
        ["resume", "T-1", "--approve", "--decline"],
        ["run", "--approve"],
        ["kb-index", "extra"],
    ],
)
def test_invalid_arguments_exit(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)
