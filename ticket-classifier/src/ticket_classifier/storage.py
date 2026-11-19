"""Files: read tickets, write and merge results."""

from pathlib import Path

from pydantic import TypeAdapter

from .models import ClassifiedTicket, Ticket

TICKETS_ADAPTER = TypeAdapter(list[Ticket])
RESULTS_ADAPTER = TypeAdapter(list[ClassifiedTicket])


def load_tickets(path: Path) -> list[Ticket]:
    """Raises ``OSError`` if unreadable, ``ValidationError`` if not valid tickets."""
    return TICKETS_ADAPTER.validate_json(path.read_text(encoding="utf-8"))


def load_results(path: Path) -> list[ClassifiedTicket]:
    """The saved results; empty if there is no file yet."""
    if not path.exists():
        return []
    return RESULTS_ADAPTER.validate_json(path.read_text(encoding="utf-8"))


def save_results(results: list[ClassifiedTicket], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(RESULTS_ADAPTER.dump_json(results, indent=2))


def merge_results(results: list[ClassifiedTicket], path: Path) -> None:
    """Add results to the saved ones; a new result replaces one with the same id."""
    new_ids = {result.ticket_id for result in results}
    kept = [result for result in load_results(path) if result.ticket_id not in new_ids]
    save_results(kept + results, path)
