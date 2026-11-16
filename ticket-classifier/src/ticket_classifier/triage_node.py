from ticket_classifier.client import get_client
from ticket_classifier.config import get_settings
from ticket_classifier.graph import TriageState
from ticket_classifier.models import Customer, Ticket, TicketClassification
from ticket_classifier.prompts import SYSTEM_PROMPT


def create_prompt(customer: Customer | None, ticket: Ticket) -> str:
    parts = ["Classify the following ticket."]

    if customer is not None:
        parts.append(f"Customer: {customer.model_dump_json()}")

    parts.append(f"<ticket>\n{ticket.text}\n</ticket>")

    return "\n".join(parts)


def node_triage(state: TriageState) -> TriageState:
    settings = get_settings()

    client = get_client()
    customer = state["customer"]
    ticket = state["ticket"]

    prompt = create_prompt(customer, ticket)

    output = client.messages.parse(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_format=TicketClassification,
    )

    parsed_output = output.content[0].parsed_output

    response = f"Triage completed. Output: {parsed_output}"

    return {
        "classification": parsed_output,
        "last_updated_by": "node_triage",
        "responses": [response],
    }
