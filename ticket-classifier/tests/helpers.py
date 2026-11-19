"""Shared test data; fixtures stay in conftest.py."""

from ticket_classifier.models import TicketClassification

HIGH = TicketClassification(category="billing", priority="high")
LOW = TicketClassification(category="billing", priority="low")
