"""Cut documents into overlapping word windows."""

from ..models import Chunk


def chunk_document(text: str, size: int, overlap: int) -> list[str]:
    """Windows of ``size`` words; each starts ``size - overlap`` words after the last.

    The last window may be shorter. It is kept, so no words are lost.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if not 0 <= overlap < size:
        raise ValueError("overlap must be at least 0 and smaller than size")

    words = text.split()
    step = size - overlap
    windows = []
    for start in range(0, len(words), step):
        windows.append(" ".join(words[start : start + size]))
        if start + size >= len(words):  # this window reached the end
            break
    return windows


def chunk_corpus(docs: dict[str, str], size: int, overlap: int) -> list[Chunk]:
    """Chunk every document; ``docs`` maps a source name to its text."""
    return [
        Chunk(source=source, ordinal=ordinal, text=text)
        for source, document in docs.items()
        for ordinal, text in enumerate(chunk_document(document, size, overlap))
    ]
