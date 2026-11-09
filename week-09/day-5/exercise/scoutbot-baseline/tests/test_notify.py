"""The ledger, and the guarantee it buys. No graph and no model anywhere in this file.

`send_reply` is the only function in the repo that does something irreversible, so it gets the most
direct tests in the repo. Every case here is about one question: how many emails does the customer
receive when our code runs more than once?

The `transport` list is why none of this needs patching. A caller can hand `send_reply` somewhere to
put the message, so "was an email sent" is a length check rather than a mock assertion, and the
function stays as ordinary as everything else in this package.
"""
import pytest

from scoutbot.notify import (
    AlreadySentError,
    Ledger,
    reply_key,
    reset_flaky_counter,
    send_reply,
)


@pytest.fixture(autouse=True)
def _fresh_counter():
    reset_flaky_counter()
    yield
    reset_flaky_counter()


def test_one_call_sends_one_email_and_records_it():
    ledger = Ledger.in_memory()
    sent = []

    outcome = send_reply("T-1", "Sorry about that.", ledger, transport=sent)

    assert outcome["sent"] is True
    assert outcome["key"] == "T-1:send_reply"
    assert len(sent) == 1
    assert ledger.already_done("T-1:send_reply") is True


def test_a_second_call_sends_nothing():
    """The whole point, in three lines."""
    ledger = Ledger.in_memory()
    sent = []

    send_reply("T-1", "Sorry about that.", ledger, transport=sent)
    outcome = send_reply("T-1", "Sorry about that.", ledger, transport=sent)

    assert outcome["skipped"] is True
    assert outcome["reason"] == "already sent"
    assert len(sent) == 1


def test_a_failure_after_the_send_still_leaves_the_ledger_row_behind():
    """The realistic failure, and the reason the record is written immediately after the send
    rather than at the end of the function.

    The gateway accepted the mail and then the connection dropped, so this call raises. The email is
    gone regardless, which means the only correct thing to have done before raising is write it
    down - and that is what makes the retry safe.
    """
    ledger = Ledger.in_memory()
    sent = []

    with pytest.raises(ConnectionError):
        send_reply("T-1", "Sorry.", ledger, fail_after_send=1, transport=sent)

    assert len(sent) == 1
    assert ledger.already_done(reply_key("T-1")) is True

    # And the retry that follows finds the row and declines.
    outcome = send_reply("T-1", "Sorry.", ledger, fail_after_send=1, transport=sent)
    assert outcome["skipped"] is True
    assert len(sent) == 1


def test_three_attempts_one_email():
    """What LangGraph's RetryPolicy does to this function, simulated by simply calling it again."""
    ledger = Ledger.in_memory()
    sent = []

    for _ in range(3):
        try:
            send_reply("T-1", "Sorry.", ledger, fail_after_send=2, transport=sent)
        except ConnectionError:
            pass

    assert len(sent) == 1
    assert len(ledger.entries()) == 1


def test_without_a_ledger_the_same_sequence_sends_three():
    """The counterfactual, asserted rather than described, because the guarantee is only
    meaningful next to what happens without it.

    A fresh ledger per attempt is exactly what "no durable record" looks like in code, and it is
    also the mistake a default argument can hide: anything that recreates the record per call
    recreates the duplicate.
    """
    sent = []

    for _ in range(3):
        try:
            send_reply("T-1", "Sorry.", Ledger.in_memory(), fail_after_send=2, transport=sent)
        except ConnectionError:
            pass

    assert len(sent) == 3


def test_the_key_is_derived_from_the_ticket_so_it_is_stable():
    """A key generated inside the function (a `uuid4()`, a timestamp) would make every attempt look
    like new work, and the ledger would dedupe nothing while appearing to work."""
    assert reply_key("T-1") == reply_key("T-1")
    assert reply_key("T-1") != reply_key("T-2")


def test_different_tickets_are_different_actions():
    ledger = Ledger.in_memory()
    sent = []

    send_reply("T-1", "Sorry.", ledger, transport=sent)
    send_reply("T-2", "Sorry.", ledger, transport=sent)

    assert len(sent) == 2
    assert len(ledger.entries()) == 2


def test_strict_mode_raises_instead_of_shrugging():
    """Normal operation treats a duplicate as ordinary, because on a retry it is. A test that wants
    to prove the guard fired asks for the exception explicitly."""
    ledger = Ledger.in_memory()
    send_reply("T-1", "Sorry.", ledger, transport=[])

    with pytest.raises(AlreadySentError):
        send_reply("T-1", "Sorry.", ledger, strict=True, transport=[])


def test_recording_the_same_key_twice_is_harmless():
    """`INSERT OR IGNORE` against a PRIMARY KEY, because "record it again" is precisely what a
    retried node tries to do."""
    ledger = Ledger.in_memory()

    ledger.record("k", "first")
    ledger.record("k", "second")

    assert len(ledger.entries()) == 1
    assert ledger.entries()[0][1] == "first"


def test_a_file_backed_ledger_outlives_the_object_that_wrote_it(tmp_path):
    """The durability that makes this work across processes. Two `Ledger.at()` calls on one path
    share nothing in memory."""
    db = tmp_path / "ledger.db"
    sent = []

    send_reply("T-1", "Sorry.", Ledger.at(db), transport=sent)
    outcome = send_reply("T-1", "Sorry.", Ledger.at(db), transport=sent)

    assert outcome["skipped"] is True
    assert len(sent) == 1


def test_an_in_memory_ledger_does_not(tmp_path):
    """The contrast, and the same trade-off as `InMemorySaver` versus `SqliteSaver` on Tuesday: an
    in-memory ledger protects a retry seconds later and nothing at all after the process ends."""
    sent = []

    send_reply("T-1", "Sorry.", Ledger.in_memory(), transport=sent)
    send_reply("T-1", "Sorry.", Ledger.in_memory(), transport=sent)

    assert len(sent) == 2
