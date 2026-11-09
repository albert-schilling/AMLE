"""The one thing in this repo that cannot be undone, and the record that keeps it to once.

Everything ScoutBot has done up to now has been safe to repeat. Looking a customer up twice is
wasteful. Triaging twice costs a few cents. Drafting twice costs a few more. Sending a customer an
email twice is a different category of mistake: it cannot be taken back, the customer sees it, and
if the email says "we have refunded you EUR 900" then somebody in finance sees it too.

That matters today because of a fact the week has been planting since Monday: **a node's code can
run more than once for one logical run.** Two ways, and neither is exotic:

1. **A resumed node restarts from its first line.** Wednesday proved it with a counter. Everything
   above the `interrupt()` call runs again.
2. **A retried node restarts from its first line.** One argument to `add_node()`, and any transient
   exception makes the whole node body run again from the top.

The first can be designed around: put the side effect in its own node below the pause, which is
exactly what `send_reply` is. The second cannot. There is no position in a graph that a retry does
not reach, because the retry re-runs the node you put it on. So the guarantee has to come from the
side effect itself, and that is what this module is.

**The obvious fix, and why it is not here.** The intuitive guard is to ask the run's own state:
`if state["sent"]: return`. Verified locally, and it does not work. A node that interrupts returns
nothing at all, so its own `{"sent": True}` was never committed, and the resumed node sees
`sent: False` and sends again. Then, once the run finally finishes, state *does* say `sent: True`,
so the guard reads as correct in every subsequent inspection. It is wrong twice and quiet about it.
The record has to live outside the run's state, written at the moment the thing happens.

**What the key has to be.** Derived from the run, never generated inside the node. A `uuid4()` on
the first line of `send_reply` produces a different key on every attempt, so every attempt looks
like new work, the ledger fills up, and it dedupes nothing. `f"{ticket_id}:send_reply"` is stable
across attempts, across processes, and across a week of the run sitting paused. The key *is* the
design; the table around it is bookkeeping.

**And the honest limit.** The order here is check, send, record. If the process dies between the
send and the record, the next attempt sends again, because nothing wrote the row. That window is
real and this module does not close it. Closing it means writing the ledger row in the same
transaction as the side effect, which is only possible when the side effect is in your own database
- and an email API is not. So what this buys is *at-least-once delivery plus deduplication*, which
is what almost every production system actually runs on, rather than the exactly-once semantics the
phrase "idempotency" tends to promise. Say so out loud when teaching it; a student who thinks they
have exactly-once will be surprised in a worse place later.
"""
import sqlite3
from pathlib import Path
from typing import Optional, Union

LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS side_effects (
    key        TEXT PRIMARY KEY,
    detail     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class AlreadySentError(RuntimeError):
    """Raised only by `send_reply(..., strict=True)`, which the tests use.

    Normal operation treats a duplicate as a no-op and says so in its return value, because
    "somebody already did this" is a completely ordinary thing to discover on a retry and not an
    error condition. A test wanting to prove the guard fired asks for it explicitly.
    """


class Ledger:
    """A durable record of side effects that already happened, keyed by a caller-chosen string.

    Backed by SQLite, in the same file the checkpointer writes to by default, for a reason worth
    saying out loud: the record of *what a run did to the outside world* belongs next to the record
    of *where the run got to*, so one file is the whole truth about a run. It also means the ledger
    inherits the durability Tuesday established, which is the property that makes it work across
    processes at all.

    `key` is the PRIMARY KEY, so the database itself refuses a duplicate. `INSERT OR IGNORE` then
    makes recording twice harmless, which matters because "record it again" is precisely what a
    retried node tries to do.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.execute(LEDGER_SCHEMA)
        self._conn.commit()

    @classmethod
    def at(cls, db_path: Union[str, Path]) -> "Ledger":
        """Open (or create) a ledger at a path. `check_same_thread=False` for the same reason as
        Tuesday's checkpointer: LangGraph may touch the connection from a worker thread."""
        return cls(sqlite3.connect(str(db_path), check_same_thread=False))

    @classmethod
    def in_memory(cls) -> "Ledger":
        """A ledger that lasts as long as the process. Fine for tests, useless for durability."""
        return cls(sqlite3.connect(":memory:", check_same_thread=False))

    def already_done(self, key: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM side_effects WHERE key = ?", (key,)
        ).fetchone()
        return row is not None

    def record(self, key: str, detail: str = "") -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO side_effects (key, detail) VALUES (?, ?)", (key, detail)
        )
        self._conn.commit()

    def entries(self) -> list:
        """Everything recorded, oldest first. Only used for printing in the demo scripts, but
        being able to `SELECT *` the ledger is most of why a table beats an in-memory set."""
        return self._conn.execute(
            "SELECT key, detail, created_at FROM side_effects ORDER BY created_at, key"
        ).fetchall()


def reply_key(ticket_id: str) -> str:
    """The idempotency key for "the reply to this ticket has been sent".

    A function rather than an f-string at the call site, so there is exactly one definition of what
    counts as the same action. If two places in the codebase spell the key slightly differently,
    the ledger stops working and nothing tells you.

    Note what it is keyed on: the *ticket*, not the attempt, not the run, not the timestamp. The
    question the key has to answer is "have we already replied to this ticket?", and that question
    is about the ticket.
    """
    return f"{ticket_id}:send_reply"


def send_reply(
    ticket_id: str,
    text: str,
    ledger: Ledger,
    fail_after_send: int = 0,
    strict: bool = False,
    transport: Optional[list] = None,
) -> dict:
    """Send the reply to the customer, at most once per ticket, however often this is called.

    Structure is the entire lesson, in four steps, and the order of the middle two is the part that
    is easy to get wrong:

        1. ask the ledger whether this already happened, and skip steps 2 and 3 if it did
        2. do the irreversible thing
        3. record that it happened, *immediately*, before anything else can fail
        4. everything else

    Step 3 goes directly after step 2 and not at the end of the function. Whatever sits between the
    send and the record is the width of the window in which a crash causes a duplicate, so that gap
    is kept as close to zero as the code can make it. A version of this function that did its
    bookkeeping on the way out would have a much wider window, and would look perfectly reasonable.

    `fail_after_send` puts a transient failure in step 4, which is where the day's central problem
    actually lives: the mail gateway accepted the message and *then* the connection dropped, so our
    code never learned that it had succeeded. A retry has every reason to try again, and only the
    ledger row from step 3 stops it.

    That positioning was worth verifying rather than assuming, and it corrected this module's first
    design. Put the transient failure *above* the send instead, and a retry never reaches the send:
    one email goes out either way and the ledger looks like pointless ceremony. Below it, the same
    retry sends three copies without a ledger and one with it. Teaching it the first way round would
    leave students with exactly the wrong instinct.

    `transport` is where a "sent" email lands, defaulting to stdout. A list makes the whole thing
    assertable in a test without patching anything, which keeps this function as ordinary as every
    node in this codebase.
    """
    key = reply_key(ticket_id)

    # 1. Has this already happened?
    already = ledger.already_done(key)
    if already and strict:
        raise AlreadySentError(f"{key} was already sent")

    if not already:
        # 2. The irreversible bit.
        if transport is None:
            print(f"  [email -> customer] re: {ticket_id}: {text[:60]}...")
        else:
            transport.append({"ticket_id": ticket_id, "text": text})

        # 3. Write it down straight away. Anything between step 2 and here is a duplicate waiting
        #    for a badly-timed crash.
        ledger.record(key, detail=f"replied to {ticket_id}")
    elif transport is None:
        print(f"  [no send] {key} is already in the ledger, so this attempt sent nothing")

    # 4. The rest of the work, which is allowed to fail, and does when asked to. Note that it runs
    #    on both paths: what drops is the connection carrying our confirmation back, and a retry has
    #    to survive that whether or not this particular attempt sent anything. Skip it on the
    #    already-sent path and a retry would succeed on its second entry, which quietly halves the
    #    demo and hides the fact that the ledger holds across every attempt rather than just one.
    if fail_after_send > 0:
        _ATTEMPTS[key] = _ATTEMPTS.get(key, 0) + 1
        if _ATTEMPTS[key] <= fail_after_send:
            raise ConnectionError(
                f"mail gateway accepted {ticket_id} and then dropped the connection"
            )

    if already:
        return {"sent": False, "skipped": True, "key": key, "reason": "already sent"}
    return {"sent": True, "skipped": False, "key": key, "reason": "sent"}


# Attempt counter for the deliberately-flaky path only. Module-level because the point is to fail
# across separate calls into the same process, which is what a retry looks like from in here.
_ATTEMPTS: dict = {}


def reset_flaky_counter() -> None:
    """Forget which tickets have already failed. Demo scripts and tests call this; nothing else."""
    _ATTEMPTS.clear()
