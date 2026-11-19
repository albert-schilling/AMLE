import pytest

from ticket_classifier.cli import main
from ticket_classifier.commands import MissingApiKeyError
from ticket_classifier.runner import BatchResult, NotPausedError


@pytest.fixture
def run(mocker):
    return mocker.patch(
        "ticket_classifier.cli.commands.run", return_value=BatchResult()
    )


@pytest.fixture
def resume(mocker):
    return mocker.patch("ticket_classifier.cli.commands.resume")


def test_run_passes_loaded_tickets(run, write_tickets):
    tickets = write_tickets([{"id": "T-1", "text": "x"}])

    assert main(["run", str(tickets)]) == 0
    assert [t.id for t in run.call_args.args[0]] == ["T-1"]


def test_run_uses_tickets_path_setting(run, write_tickets, monkeypatch):
    monkeypatch.setenv("TICKETS_PATH", str(write_tickets([{"id": "T-1", "text": "x"}])))

    assert main(["run"]) == 0
    assert [t.id for t in run.call_args.args[0]] == ["T-1"]


def test_run_returns_1_on_failures(run, write_tickets):
    run.return_value = BatchResult(failed=["T-1"])

    assert main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))]) == 1


def test_run_paused_tickets_are_not_failures(run, write_tickets):
    run.return_value = BatchResult(paused=["T-1"])

    assert main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))]) == 0


def test_run_returns_2_on_invalid_tickets_file(run, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")

    assert main(["run", str(bad)]) == 2
    run.assert_not_called()


def test_run_returns_2_on_missing_tickets_file(run, tmp_path):
    assert main(["run", str(tmp_path / "missing.json")]) == 2
    run.assert_not_called()


@pytest.mark.parametrize(
    ("flag", "approved"), [("--approve", True), ("--decline", False)]
)
def test_resume_passes_the_answer(resume, flag, approved):
    assert main(["resume", "T-1", flag, "--note", "ok"]) == 0

    ticket_id, answer, _ = resume.call_args.args
    assert ticket_id == "T-1"
    assert answer == {"approved": approved, "note": "ok"}


def test_resume_returns_2_without_paused_run(resume):
    resume.side_effect = NotPausedError("Ticket T-9 has no paused run")

    assert main(["resume", "T-9", "--approve"]) == 2


def test_run_without_api_key_returns_2(run, write_tickets):
    run.side_effect = MissingApiKeyError("ANTHROPIC_API_KEY is not set")

    assert main(["run", str(write_tickets([{"id": "T-1", "text": "x"}]))]) == 2
