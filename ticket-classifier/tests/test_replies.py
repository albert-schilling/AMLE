import pytest
from helpers import REFUND_PASSAGE, reply_message

from ticket_classifier.models import Citation
from ticket_classifier.replies import ReplyError, build_reply

SHIPPING_PASSAGE = REFUND_PASSAGE.model_copy(
    update={"source": "shipping.md", "ordinal": 0, "text": "Free over 50 euros."}
)
PASSAGES = [REFUND_PASSAGE, SHIPPING_PASSAGE]


def test_reply_without_citations_has_no_sources():
    reply = build_reply(reply_message({"text": "We are looking into it."}), [])

    assert reply.text == "We are looking into it."
    assert reply.citations == []
    assert not reply.has_sources


def test_cited_parts_get_numbers_in_order_of_first_use_and_a_source_list():
    message = reply_message(
        {"text": "Shipping is free. ", "cited": [(1, "Free over 50 euros.")]},
        {"text": "Refunds take 5 days.", "cited": [(0, "Refunds take 5 business")]},
        {"text": " Again: free.", "cited": [(1, "Free over 50")]},
    )

    reply = build_reply(message, PASSAGES)

    assert reply.text == (
        "Shipping is free. [1] Refunds take 5 days. [2] Again: free. [1]"
        "\n\nSources:\n[1] shipping.md, part 0\n[2] refunds.md, part 1"
    )
    assert reply.citations == [
        Citation(
            source="shipping.md",
            ordinal=0,
            quotes=["Free over 50 euros.", "Free over 50"],
        ),
        Citation(source="refunds.md", ordinal=1, quotes=["Refunds take 5 business"]),
    ]
    assert reply.has_sources


def test_one_part_citing_two_passages_gets_both_markers():
    message = reply_message(
        {"text": "Both apply.", "cited": [(0, "Refunds"), (1, "Free")]}
    )

    assert build_reply(message, PASSAGES).text.startswith("Both apply. [1][2]\n")


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_refused_or_cut_off_answer_is_no_reply(stop_reason):
    with pytest.raises(ReplyError, match=stop_reason):
        build_reply(reply_message(stop_reason=stop_reason), [])


def test_citation_of_a_search_result_that_was_not_sent_fails():
    message = reply_message({"text": "x", "cited": [(2, "invented")]})

    with pytest.raises(ReplyError, match="not sent"):
        build_reply(message, PASSAGES)


def test_answer_without_text_fails():
    with pytest.raises(ReplyError, match="no text"):
        build_reply(reply_message({"text": "  "}), [])
