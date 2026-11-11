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


def test_thinking_defaults():
    settings = Settings()
    assert settings.thinking_budget == 2000
    assert settings.max_tokens == 4000


def test_thinking_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("THINKING_BUDGET", "0")
    assert Settings().thinking_budget == 0


def test_thinking_budget_must_reach_api_minimum(monkeypatch):
    monkeypatch.setenv("THINKING_BUDGET", "500")
    monkeypatch.setenv("MAX_TOKENS", "4000")
    with pytest.raises(ValidationError, match="1024"):
        Settings()


def test_thinking_budget_must_be_below_max_tokens(monkeypatch):
    monkeypatch.setenv("THINKING_BUDGET", "2000")
    monkeypatch.setenv("MAX_TOKENS", "2000")
    with pytest.raises(ValidationError, match="below MAX_TOKENS"):
        Settings()


def test_valid_thinking_budget(monkeypatch):
    monkeypatch.setenv("THINKING_BUDGET", "2000")
    monkeypatch.setenv("MAX_TOKENS", "4000")
    assert Settings().thinking_budget == 2000
