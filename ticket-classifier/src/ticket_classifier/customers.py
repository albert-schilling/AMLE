"""Customer data access. Swap the body of ``get_customer`` to use a database later."""

import json
from functools import cache
from pathlib import Path
from typing import Any

from .config import get_settings
from .models import Customer


@cache
def load_customers(path: Path) -> dict[str, dict[str, Any]]:
    """Raw records by customer id; ``get_customer`` validates one when it is used."""
    records: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return records


def get_customer(customer_id: str) -> Customer | None:
    """Return the customer, or None if unknown.

    Raises ``pydantic.ValidationError`` if the stored record is malformed.
    """
    record = load_customers(get_settings().customers_path).get(customer_id)
    return None if record is None else Customer.model_validate(record)
