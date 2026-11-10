from pathlib import Path

from pydantic import TypeAdapter

from .models import ClassifiedTicket, Ticket

TICKETS_ADAPTER = TypeAdapter(list[Ticket])
RESULTS_ADAPTER = TypeAdapter(list[ClassifiedTicket])


def load_tickets(path: Path) -> list[Ticket]:
    return TICKETS_ADAPTER.validate_json(path.read_text(encoding="utf-8"))


def save_results(results: list[ClassifiedTicket], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(RESULTS_ADAPTER.dump_json(results, indent=2))
