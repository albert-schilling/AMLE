import pytest

from ticket_classifier.knowledge import NoDocumentsError, load_documents


def test_loads_markdown_files_sorted_by_name(tmp_path):
    (tmp_path / "shipping.md").write_text("ship")
    (tmp_path / "refunds.md").write_text("refund")
    (tmp_path / "notes.txt").write_text("not a policy")

    assert list(load_documents(tmp_path).items()) == [
        ("refunds.md", "refund"),
        ("shipping.md", "ship"),
    ]


def test_folder_without_markdown_files_is_an_error(tmp_path):
    (tmp_path / "notes.txt").write_text("x")

    with pytest.raises(NoDocumentsError):
        load_documents(tmp_path)


def test_missing_folder_is_an_error(tmp_path):
    with pytest.raises(NoDocumentsError):
        load_documents(tmp_path / "missing")
