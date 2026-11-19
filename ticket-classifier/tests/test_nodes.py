import logging

from ticket_classifier.models import NotEscalated
from ticket_classifier.nodes import node_get_customer, node_mark_handled


def test_customer_found(customers_file, make_ticket):
    update = node_get_customer({"ticket": make_ticket(customer_id="1001")})

    assert update["customer"].first_name == "Alice"


def test_ticket_without_customer_id(customers_file, make_ticket):
    update = node_get_customer({"ticket": make_ticket(customer_id=None)})

    assert update == {"customer": None}


def test_unknown_customer_is_logged(customers_file, make_ticket, caplog):
    update = node_get_customer({"ticket": make_ticket(customer_id="9999")})

    assert update == {"customer": None}
    assert ("Customer 9999 not found", logging.WARNING) in [
        (r.getMessage(), r.levelno) for r in caplog.records
    ]


def test_malformed_customer_record_is_logged(customers_file, make_ticket, caplog):
    customers_file.write_text('{"1001": {"id": "1001"}}')

    update = node_get_customer({"ticket": make_ticket(customer_id="1001")})

    assert update == {"customer": None}
    assert caplog.records[-1].levelno == logging.ERROR


def test_mark_handled_sets_no_escalation():
    assert node_mark_handled({}) == {"escalation": NotEscalated()}
