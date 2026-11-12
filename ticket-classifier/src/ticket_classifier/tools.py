import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from anthropic import beta_tool
from anthropic.lib.tools import BetaFunctionTool
from pydantic import TypeAdapter, ValidationError

from .config import get_settings
from .customers import get_customer
from .models import Payment
from .payments import find_duplicates
from .safe_fetch import FetchRefused, fetch_text

logger = logging.getLogger(__name__)


@beta_tool
def lookup_customer(customer_id: str) -> str:
    """Look up a customer by id. Returns customer JSON or an error message."""
    logger.info("Looking up customer %s", customer_id)

    try:
        customer = get_customer(customer_id)
    except ValidationError:
        logger.exception("Customer record %s is malformed", customer_id)
        return "Customer record unavailable"

    if customer is None:
        logger.warning("Customer %s not found", customer_id)
        return "Customer not found"

    return customer.model_dump_json()


PAYMENTS_ADAPTER = TypeAdapter(list[Payment])


@beta_tool
def find_duplicate_charges(client_id: str, payments: list[dict[str, Any]]) -> str:
    """Find duplicate charges of one client: same amount within 24 hours.

    Pass the rows of the payments JSON you fetched with web_fetch. Never count
    duplicates yourself: report only what this tool returns.
    """
    logger.info("Checking %d payment rows of client %s", len(payments), client_id)
    try:
        rows = PAYMENTS_ADAPTER.validate_python(payments)
    except ValidationError:
        logger.exception("Payment rows are malformed")
        return "Invalid payment rows: need client_id, invoice_number, amount, timestamp"

    pairs = find_duplicates(rows, client_id)
    if not pairs:
        return f"No duplicate charges found for client {client_id}"
    return json.dumps(
        [
            {
                "invoices": [first.invoice_number, second.invoice_number],
                "amount": str(first.amount),
                "seconds_apart": int(
                    (second.timestamp - first.timestamp).total_seconds()
                ),
            }
            for first, second in pairs
        ]
    )


@dataclass
class Escalation:
    """Human gate and outcome of ``escalate_to_human`` for one ticket."""

    approve: Callable[[str], bool]
    reason: str | None = None  # set once a human approved


def make_escalation_tool(escalation: Escalation) -> BetaFunctionTool[Any]:
    """Build ``escalate_to_human``. It only counts once a human approves.

    A rejection is returned to the model as a normal observation so the loop
    continues. After an approval, further calls are answered without asking again.
    """

    @beta_tool
    def escalate_to_human(reason: str) -> str:
        """Hand the ticket to a human agent. Needs approval and may be rejected."""
        logger.info("Escalation requested: %s", reason)
        if escalation.reason is not None:
            return "Already escalated. A human will take over this ticket."
        if not escalation.approve(reason):
            return "Escalation rejected by the human. Continue without escalating."
        escalation.reason = reason
        return "Escalation approved. A human will take over this ticket."

    return escalate_to_human


def make_local_fetch_tool() -> BetaFunctionTool[Any]:
    """Our own ``web_fetch``: runs here via httpx, so ``safe_fetch`` is the sandbox.

    One tool per ticket: it counts its calls and stops at ``WEB_FETCH_MAX_USES``.
    """
    settings = get_settings()
    allowed_hosts = {settings.status_domain.lower(), settings.payments_domain.lower()}
    calls = 0

    @beta_tool(name="web_fetch")
    def web_fetch(url: str) -> str:
        """Fetch one page from an allowed host and return its text."""
        nonlocal calls
        calls += 1
        logger.info("Local fetch %d: %s", calls, url)
        if calls > settings.web_fetch_max_uses:
            return "Fetch limit reached for this ticket"
        try:
            body = fetch_text(url, allowed_hosts)
        except FetchRefused as error:
            logger.warning("Fetch refused: %s", error)
            return f"Fetch refused: {error}"
        return f'<fetched url="{url}">\n{body}\n</fetched>'

    return web_fetch


def make_code_execution_tool() -> dict[str, Any]:
    """Anthropic's server-side code execution tool (a sandboxed Linux container).

    The container has no internet, 5 GiB RAM, 1 CPU and an execution time limit that
    we cannot change. The tool has no ``max_uses``; the loop cap and the prompt limit
    how often it runs.
    """
    return {"type": "code_execution_20250825", "name": "code_execution"}


def make_fetch_tool() -> dict[str, Any] | BetaFunctionTool[Any]:
    """The fetch tool for ``FETCH_BACKEND``: Anthropic's server tool or our own."""
    if get_settings().fetch_backend == "local":
        return make_local_fetch_tool()
    return make_web_fetch_tool()


def make_web_fetch_tool() -> dict[str, Any]:
    """Anthropic's server-side ``web_fetch`` tool, locked down by guardrails.

    Anthropic runs the fetch (our sandbox); it can only reach ``STATUS_DOMAIN`` and
    ``PAYMENTS_DOMAIN``, at most ``WEB_FETCH_MAX_USES`` times per ticket, and the page
    size is capped.
    """
    settings = get_settings()
    return {
        "type": "web_fetch_20250910",
        "name": "web_fetch",
        "max_uses": settings.web_fetch_max_uses,
        "allowed_domains": [settings.status_domain, settings.payments_domain],
        "max_content_tokens": settings.web_fetch_max_content_tokens,
    }
