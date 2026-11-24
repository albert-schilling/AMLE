import pytest
from pydantic import ValidationError

from ticket_classifier.config import Settings


@pytest.mark.parametrize("overlap", [60, 61])
def test_overlap_must_be_smaller_than_chunk_size(monkeypatch, overlap):
    monkeypatch.setenv("CHUNK_SIZE", "60")
    monkeypatch.setenv("CHUNK_OVERLAP", str(overlap))

    with pytest.raises(ValidationError, match="chunk_overlap must be smaller"):
        Settings()


def test_overlap_below_chunk_size_is_accepted(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE", "60")
    monkeypatch.setenv("CHUNK_OVERLAP", "59")

    assert Settings().chunk_overlap == 59


def test_database_url_is_hidden_when_printed(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", "postgresql://u:secret@localhost/db")

    settings = Settings()

    assert "secret" not in repr(settings)
    assert "secret" in settings.knowledge_database_url.get_secret_value()
