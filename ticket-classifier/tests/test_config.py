import pytest
from pydantic import ValidationError

from ticket_classifier.config import Settings


def test_settings_require_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_invalid_log_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults():
    settings = Settings()
    assert settings.max_iterations == 6
    assert str(settings.results_path) == "output/results.json"
