import json

import pytest
from helpers import LOW

from ticket_classifier import customers
from ticket_classifier.config import get_settings
from ticket_classifier.models import Ticket

CUSTOMERS = {
    "1001": {
        "id": "1001",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        "account_age_days": 430,
        "past_refunds_90d": 2,
        "plan": "pro",
        "products": ["Wendel", "Pip"],
    }
}


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Keep tests independent of the developer's real .env and API key.

    Relative default paths (``output/...``) land in ``tmp_path`` too.
    """
    monkeypatch.chdir(tmp_path)  # so no .env is picked up
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    customers.load_customers.cache_clear()
    yield
    get_settings.cache_clear()
    customers.load_customers.cache_clear()


@pytest.fixture
def make_ticket():
    def _make(customer_id="1001", text="Test ticket", id="T-1"):
        return Ticket(id=id, customer_id=customer_id, text=text)

    return _make


@pytest.fixture
def customers_file(monkeypatch, tmp_path):
    path = tmp_path / "customers.json"
    path.write_text(json.dumps(CUSTOMERS))
    monkeypatch.setenv("CUSTOMERS_PATH", str(path))
    return path


@pytest.fixture
def results_file(monkeypatch, tmp_path):
    path = tmp_path / "out" / "results.json"
    monkeypatch.setenv("RESULTS_PATH", str(path))
    return path


@pytest.fixture
def write_tickets(tmp_path):
    def _write(tickets):
        path = tmp_path / "tickets.json"
        path.write_text(json.dumps(tickets))
        return path

    return _write


@pytest.fixture
def model(mocker, customers_file):
    """Mock the triage call; returns the mocked ``parse`` to count calls.

    The ticket text picks the outcome via ``model.outcomes[text]``, default ``LOW``.
    An outcome is a classification, None (no parsed output) or an exception.
    """
    outcomes = {}
    client = mocker.patch("ticket_classifier.nodes.triage.get_client").return_value

    def parse(**kwargs):
        text = kwargs["messages"][0]["content"].split("<ticket>\n")[1].split("\n")[0]
        outcome = outcomes.get(text, LOW)
        if isinstance(outcome, Exception):
            raise outcome
        stop_reason = "max_tokens" if outcome is None else "end_turn"
        return mocker.Mock(parsed_output=outcome, stop_reason=stop_reason)

    client.messages.parse.side_effect = parse
    client.messages.parse.outcomes = outcomes
    return client.messages.parse
