import pytest

from ticket_classifier.knowledge.chunking import chunk_corpus, chunk_document
from ticket_classifier.models import Chunk

TEN_WORDS = "w0 w1 w2 w3 w4 w5 w6 w7 w8 w9"


def test_windows_overlap_and_keep_the_short_tail():
    assert chunk_document(TEN_WORDS, size=4, overlap=1) == [
        "w0 w1 w2 w3",
        "w3 w4 w5 w6",
        "w6 w7 w8 w9",
    ]
    assert chunk_document(TEN_WORDS, size=4, overlap=2) == [
        "w0 w1 w2 w3",
        "w2 w3 w4 w5",
        "w4 w5 w6 w7",
        "w6 w7 w8 w9",
    ]
    assert chunk_document(TEN_WORDS, size=4, overlap=0) == [
        "w0 w1 w2 w3",
        "w4 w5 w6 w7",
        "w8 w9",
    ]


def test_no_window_only_repeats_the_end_of_the_previous_one():
    assert chunk_document("a b c d e", size=4, overlap=2) == ["a b c d", "c d e"]


def test_short_document_is_one_chunk():
    assert chunk_document("a b", size=60, overlap=10) == ["a b"]


def test_line_breaks_and_extra_spaces_become_single_spaces():
    assert chunk_document("# Title\n\nfirst   line\nsecond", size=10, overlap=0) == [
        "# Title first line second"
    ]


def test_empty_document_has_no_chunks():
    assert chunk_document(" \n ", size=4, overlap=1) == []


@pytest.mark.parametrize(("size", "overlap"), [(4, 4), (4, 5), (4, -1), (0, 0)])
def test_invalid_size_or_overlap_is_rejected(size, overlap):
    with pytest.raises(ValueError):
        chunk_document(TEN_WORDS, size=size, overlap=overlap)


def test_corpus_chunks_carry_source_and_position():
    docs = {"refunds.md": "a b c d e f", "shipping.md": "x y"}

    assert chunk_corpus(docs, size=4, overlap=0) == [
        Chunk(source="refunds.md", ordinal=0, text="a b c d"),
        Chunk(source="refunds.md", ordinal=1, text="e f"),
        Chunk(source="shipping.md", ordinal=0, text="x y"),
    ]
