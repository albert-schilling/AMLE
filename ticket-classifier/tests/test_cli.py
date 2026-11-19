import json

import pytest

from ticket_classifier.batch import BatchResult
from ticket_classifier.cli import main
from ticket_classifier.models import ResolvedTicket
from ticket_classifier.storage import save_results


def classified(ticket_id):
    return ResolvedTicket(ticket_id=ticket_id, category="other", priority="low")


def patch_pipeline(mocker, batch):
    return mocker.patch("ticket_classifier.cli.classify_all", return_value=batch)


def test_main_writes_results(mocker, write_tickets, results_file):
    tickets = write_tickets([{"id": "T-1", "customer_id": "1001", "text": "x"}])
    patch_pipeline(
        mocker,
        BatchResult(
            classified=[
                ResolvedTicket(
                    ticket_id="T-1",
                    customer_id="1001",
                    category="billing",
                    priority="high",
                )
            ]
        ),
    )

    assert main([str(tickets)]) == 0
    assert json.loads(results_file.read_text()) == [
        {
            "ticket_id": "T-1",
            "customer_id": "1001",
            "category": "billing",
            "priority": "high",
            "escalated": False,
            "escalation_reason": None,
        }
    ]


def test_main_overwrites_previous_results(mocker, write_tickets, results_file):
    results_file.parent.mkdir()
    results_file.write_text('[{"stale": true}]')
    tickets = write_tickets([{"id": "T-1", "text": "x"}])
    patch_pipeline(mocker, BatchResult(classified=[classified("T-1")]))

    main([str(tickets)])

    assert [r["ticket_id"] for r in json.loads(results_file.read_text())] == ["T-1"]


def test_main_returns_1_on_failures_but_saves_rest(mocker, write_tickets, results_file):
    tickets = write_tickets([{"id": "T-1", "text": "a"}, {"id": "T-2", "text": "b"}])
    patch_pipeline(mocker, BatchResult(classified=[classified("T-2")], failed=["T-1"]))

    assert main([str(tickets)]) == 1
    assert [r["ticket_id"] for r in json.loads(results_file.read_text())] == ["T-2"]


def test_main_uses_tickets_path_setting(
    mocker, write_tickets, monkeypatch, results_file
):
    monkeypatch.setenv("TICKETS_PATH", str(write_tickets([{"id": "T-1", "text": "x"}])))
    classify_all = patch_pipeline(mocker, BatchResult())

    assert main([]) == 0
    assert [t.id for t in classify_all.call_args.args[0]] == ["T-1"]


def test_main_returns_2_on_invalid_tickets_file(mocker, tmp_path, results_file):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    classify_all = patch_pipeline(mocker, BatchResult())

    assert main([str(bad)]) == 2
    classify_all.assert_not_called()
    assert not results_file.exists()


def test_main_returns_2_on_missing_tickets_file(mocker, tmp_path, results_file):
    patch_pipeline(mocker, BatchResult())

    assert main([str(tmp_path / "missing.json")]) == 2


def test_main_resume_runs_only_that_ticket_with_the_answer(
    mocker, write_tickets, results_file
):
    tickets = write_tickets([{"id": "T-1", "text": "a"}, {"id": "T-2", "text": "b"}])
    classify_all = patch_pipeline(mocker, BatchResult(classified=[classified("T-2")]))

    assert main([str(tickets), "--resume", "T-2", "--approve", "--note", "ok"]) == 0

    assert [t.id for t in classify_all.call_args.args[0]] == ["T-2"]
    assert classify_all.call_args.kwargs["answers"] == {
        "T-2": {"approved": True, "note": "ok"}
    }


def test_main_resume_keeps_other_saved_results(mocker, write_tickets, results_file):
    save_results([classified("T-1")], results_file)
    tickets = write_tickets([{"id": "T-2", "text": "b"}])
    patch_pipeline(mocker, BatchResult(classified=[classified("T-2")]))

    main([str(tickets), "--resume", "T-2", "--decline"])

    saved = [r["ticket_id"] for r in json.loads(results_file.read_text())]
    assert saved == ["T-1", "T-2"]


def test_main_resume_unknown_ticket_returns_2(mocker, write_tickets, results_file):
    tickets = write_tickets([{"id": "T-1", "text": "a"}])
    classify_all = patch_pipeline(mocker, BatchResult())

    assert main([str(tickets), "--resume", "T-9", "--approve"]) == 2
    classify_all.assert_not_called()


def test_main_resume_needs_a_decision(write_tickets):
    tickets = write_tickets([{"id": "T-1", "text": "a"}])

    with pytest.raises(SystemExit):
        main([str(tickets), "--resume", "T-1"])


def test_main_decision_needs_resume(write_tickets):
    tickets = write_tickets([{"id": "T-1", "text": "a"}])

    with pytest.raises(SystemExit):
        main([str(tickets), "--approve"])
