import pytest

from ticket_classifier.approval import console_approval


@pytest.mark.parametrize(
    ("answer", "expected"), [("y", True), ("YES", True), ("n", False), ("", False)]
)
def test_console_approval(monkeypatch, answer, expected):
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    assert console_approval("reason") is expected


def test_console_approval_without_terminal_denies(monkeypatch):
    def raise_eof(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert console_approval("reason") is False
