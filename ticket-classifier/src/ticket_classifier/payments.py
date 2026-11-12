from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from .models import Payment

DUPLICATE_WINDOW = timedelta(hours=24)


def find_duplicates(
    payments: list[Payment], client_id: str, window: timedelta = DUPLICATE_WINDOW
) -> list[tuple[Payment, Payment]]:
    """Pairs of charges of one client with the same amount within ``window``.

    Rows of other clients are ignored. Only neighbours in time are paired, so
    three identical charges give two pairs.
    """
    by_amount: dict[Decimal, list[Payment]] = defaultdict(list)
    for payment in payments:
        if payment.client_id == client_id:
            by_amount[payment.amount].append(payment)

    pairs = []
    for same_amount in by_amount.values():
        same_amount.sort(key=lambda payment: payment.timestamp)
        for first, second in zip(same_amount, same_amount[1:], strict=False):
            if second.timestamp - first.timestamp <= window:
                pairs.append((first, second))
    return sorted(pairs, key=lambda pair: pair[0].timestamp)
