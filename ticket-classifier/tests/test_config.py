import pytest
from pydantic import ValidationError

from ticket_classifier.config import Settings


def test_api_key_is_optional(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    assert Settings().anthropic_api_key is None


def test_settings_reject_invalid_log_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults():
    settings = Settings()
    assert settings.max_tokens == 4000
    assert str(settings.results_path) == "output/results.json"
