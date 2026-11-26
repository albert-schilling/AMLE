"""The search query call; the Anthropic client is mocked."""

import pytest
from helpers import WEAK_PASSAGE, retrieved
from pydantic import ValidationError

from ticket_classifier.config import get_settings
from ticket_classifier.models import Retrieval, SearchQuery
from ticket_classifier.prompts import QUERY_SYSTEM_PROMPT, REWORD_SYSTEM_PROMPT
from ticket_classifier.queries import write_query


@pytest.fixture
def parse(mocker):
    """The mocked ``messages.parse``; answers the query "refund double charge"."""
    client = mocker.patch("ticket_classifier.queries.get_client").return_value
    client.messages.parse.return_value = mocker.Mock(
        parsed_output=SearchQuery(query=" refund double charge "),
        stop_reason="end_turn",
    )
    return client.messages.parse


def test_first_query_uses_the_opening_prompt(parse, make_ticket):
    query = write_query(make_ticket(text="Charged twice!"), Retrieval())

    assert query == "refund double charge"
    kwargs = parse.call_args.kwargs
    assert kwargs["system"] == QUERY_SYSTEM_PROMPT
    assert kwargs["output_format"] is SearchQuery
    assert kwargs["messages"][0]["content"].endswith(
        "<ticket>\nCharged twice!\n</ticket>"
    )


def test_reword_shows_what_failed(parse, make_ticket):
    failed = retrieved(weak=[WEAK_PASSAGE], queries=["charged twice"]).judged(False)
    write_query(make_ticket(), failed)

    kwargs = parse.call_args.kwargs
    content = kwargs["messages"][0]["content"]
    assert kwargs["system"] == REWORD_SYSTEM_PROMPT
    assert "<tried_queries>\n- charged twice\n</tried_queries>" in content
    assert WEAK_PASSAGE.text in content
    assert content.index("</policies>") < content.index("<ticket>")  # ticket last


def test_uses_query_model_or_else_model(parse, make_ticket, monkeypatch):
    monkeypatch.setenv("MODEL", "main-model")
    write_query(make_ticket(), Retrieval())
    monkeypatch.setenv("QUERY_MODEL", "query-model")
    get_settings.cache_clear()
    write_query(make_ticket(), Retrieval())

    models = [call.kwargs["model"] for call in parse.call_args_list]
    assert models == ["main-model", "query-model"]


@pytest.mark.parametrize("answer", [None, SearchQuery(query="  ")])
def test_no_usable_query_falls_back_to_the_ticket_text(
    parse, make_ticket, mocker, answer
):
    parse.return_value = mocker.Mock(parsed_output=answer, stop_reason="refusal")

    assert (
        write_query(make_ticket(text="Charged twice!"), Retrieval()) == "Charged twice!"
    )


def test_invalid_output_falls_back_to_the_ticket_text(parse, make_ticket):
    with pytest.raises(ValidationError) as caught:
        SearchQuery.model_validate_json("not json")
    parse.side_effect = caught.value

    assert (
        write_query(make_ticket(text="Charged twice!"), Retrieval()) == "Charged twice!"
    )
