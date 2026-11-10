import json

import pytest
from pydantic import ValidationError

from ticket_classifier.customers import get_customer


def test_get_customer_found(customers_file):
    customer = get_customer("1001")
    assert customer is not None
    assert customer.first_name == "Alice"


def test_get_customer_unknown(customers_file):
    assert get_customer("9999") is None


def test_get_customer_malformed_record_raises(customers_file):
    customers_file.write_text(json.dumps({"1001": {"id": "1001"}}))
    with pytest.raises(ValidationError):
        get_customer("1001")


def test_customers_file_is_read_once(customers_file):
    get_customer("1001")
    customers_file.write_text("{}")
    assert get_customer("1001") is not None  # served from cache
