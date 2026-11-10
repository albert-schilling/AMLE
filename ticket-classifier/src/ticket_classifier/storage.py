from pathlib import Path

from pydantic import TypeAdapter

from .models import ClassifiedTicket, Ticket

_tickets = TypeAdapter(list[Ticket])
_results = TypeAdapter(list[ClassifiedTicket])


def load_tickets(path: Path) -> list[Ticket]:
    return _tickets.validate_json(path.read_text(encoding="utf-8"))


def save_results(results: list[ClassifiedTicket], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_results.dump_json(results, indent=2))
