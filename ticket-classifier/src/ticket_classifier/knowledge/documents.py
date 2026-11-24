"""Read the policy documents of the knowledge base."""

from pathlib import Path


class NoDocumentsError(FileNotFoundError):
    """The knowledge base folder is missing or has no .md files."""


def load_documents(folder: Path) -> dict[str, str]:
    """Every ``*.md`` file in ``folder``, as {file name: text}, sorted by name."""
    paths = sorted(folder.glob("*.md")) if folder.is_dir() else []
    if not paths:
        raise NoDocumentsError(f"No .md files in {folder}")
    return {path.name: path.read_text(encoding="utf-8") for path in paths}
