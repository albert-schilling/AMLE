import json
from types import SimpleNamespace

import pytest

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
    """Keep tests independent of the developer's real .env and API key."""
    monkeypatch.chdir(tmp_path)  # so no .env is picked up
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    customers.clear_cache()
    yield
    get_settings.cache_clear()
    customers.clear_cache()


@pytest.fixture
def mock_client(mocker):
    return mocker.Mock()


class FakeRunner:
    """Stands in for the SDK tool runner: yields messages, then ends."""

    def __init__(self, messages, observations=None):
        self.messages = messages
        self.observations = observations or [None] * len(messages)
        self._index = -1

    def __iter__(self):
        for index, message in enumerate(self.messages):
            self._index = index
            yield message

    def generate_tool_call_response(self):
        return self.observations[self._index]

    def until_done(self):
        return self.messages[-1]


def thinking(content):
    return SimpleNamespace(type="thinking", thinking=content)


def text(content):
    return SimpleNamespace(type="text", text=content)


def tool_use(name, **tool_input):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input)


def message(*blocks, stop_reason="end_turn", parsed_output=None):
    return SimpleNamespace(
        content=list(blocks), stop_reason=stop_reason, parsed_output=parsed_output
    )


def observation(content):
    return {"content": [{"type": "tool_result", "content": content}]}


@pytest.fixture
def runner_returns(mock_client):
    """Make the fake client return a FakeRunner over the given messages."""

    def _set(messages, observations=None):
        runner = FakeRunner(messages, observations)
        mock_client.beta.messages.tool_runner.return_value = runner
        return runner

    return _set


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
