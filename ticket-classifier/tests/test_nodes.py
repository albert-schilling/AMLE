from ticket_classifier.nodes import node_get_customer


def test_customer_found(customers_file, make_ticket):
    update = node_get_customer({"ticket": make_ticket(customer_id="1001")})

    assert update["customer"].first_name == "Alice"
    assert update["responses"] == ["Successfully retrieved customer with ID: 1001"]


def test_ticket_without_customer_id(customers_file, make_ticket):
    update = node_get_customer({"ticket": make_ticket(customer_id=None)})

    assert update["customer"] is None
    assert update["responses"] == ["Ticket has no customer ID."]


def test_unknown_customer_is_not_reported_as_success(customers_file, make_ticket):
    update = node_get_customer({"ticket": make_ticket(customer_id="9999")})

    assert update["customer"] is None
    assert update["responses"] == ['Customer with ID "9999" not found.']


def test_lookup_error_is_reported(customers_file, make_ticket):
    customers_file.write_text('{"1001": {"id": "1001"}}')  # malformed record

    update = node_get_customer({"ticket": make_ticket(customer_id="1001")})

    assert update["customer"] is None
    assert update["responses"] == ['Failed to get customer with ID "1001".']
