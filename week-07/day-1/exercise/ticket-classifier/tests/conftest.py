import pytest

from ticket_classifier.config import get_settings


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Keep tests independent of the developer's real .env and API key."""
    monkeypatch.chdir(tmp_path)  # so no .env is picked up
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_client(mocker):
    return mocker.Mock()
