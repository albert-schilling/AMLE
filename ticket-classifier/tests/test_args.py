from pathlib import Path

import pytest

from ticket_classifier.args import (
    KbEvalArgs,
    KbIndexArgs,
    ResumeArgs,
    RunArgs,
    parse_args,
)


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


def test_kb_eval_compares_every_size_with_every_overlap_by_default():
    args = parse_args(["kb-eval"])

    assert len(args.chunk_settings) == 9
    assert (30, 20) in args.chunk_settings


def test_kb_eval_skips_overlaps_not_smaller_than_the_size():
    args = parse_args(["kb-eval", "--sizes", "10", "20", "--overlaps", "0", "10"])

    assert args == KbEvalArgs(
        sizes=[10, 20], overlaps=[0, 10], thresholds=[0.5, 0.55, 0.6, 0.65, 0.7]
    )
    assert args.chunk_settings == [(10, 0), (20, 0), (20, 10)]


def test_kb_eval_takes_thresholds():
    assert parse_args(["kb-eval", "--thresholds", "0.6", "-0.1"]).thresholds == [
        0.6,
        -0.1,
    ]


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
        ["kb-eval", "--sizes", "0"],
        ["kb-eval", "--overlaps", "-1"],
        ["kb-eval", "--thresholds", "1.5"],
        ["kb-eval", "--sizes", "10", "--overlaps", "10"],  # nothing left to compare
    ],
)
def test_invalid_arguments_exit(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)
