import json

from ticket_classifier.batch import BatchResult
from ticket_classifier.cli import main
from ticket_classifier.models import ClassifiedTicket


def classified(ticket_id):
    return ClassifiedTicket(ticket_id=ticket_id, category="other", priority="low")


def patch_pipeline(mocker, batch):
    mocker.patch("ticket_classifier.cli.create_client")
    return mocker.patch("ticket_classifier.cli.classify_all", return_value=batch)


def test_main_writes_results(mocker, write_tickets, results_file):
    tickets = write_tickets([{"id": "T-1", "customer_id": "1001", "text": "x"}])
    patch_pipeline(
        mocker,
        BatchResult(
            classified=[
                ClassifiedTicket(
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
