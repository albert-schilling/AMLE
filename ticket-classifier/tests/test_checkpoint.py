from types import SimpleNamespace

import pytest

from ticket_classifier.checkpoint import (
    CHECKPOINT_SERDE,
    open_checkpointer,
    run_status,
    thread_config,
)
from ticket_classifier.models import (
    Citation,
    KnowledgePassage,
    Reply,
    RetrievalResult,
    Search,
    Ticket,
    TicketClassification,
)


def test_open_checkpointer_creates_the_file(tmp_path):
    path = tmp_path / "out" / "checkpoints.db"

    with open_checkpointer(path) as checkpointer:
        assert checkpointer.get_tuple(thread_config("T-1")) is None

    assert path.exists()


@pytest.mark.parametrize(
    ("interrupts", "next_nodes", "values", "status"),
    [
        ((), (), {}, "new"),
        (("interrupt",), ("human_review",), {"ticket": 1}, "paused"),
        ((), ("triage",), {"ticket": 1}, "unfinished"),
        ((), (), {"ticket": 1}, "finished"),
    ],
)
def test_run_status(interrupts, next_nodes, values, status):
    saved = SimpleNamespace(interrupts=interrupts, next=next_nodes, values=values)

    assert run_status(saved) == status


def test_escalation_request_with_models_survives_the_serializer():
    request = {
        "question": "?",
        "answer_format": {"approved": "bool", "note": "str"},
        "ticket": Ticket(id="T-1", text="x"),
        "customer": None,
        "classification": TicketClassification(category="billing", priority="high"),
        "policies": [
            KnowledgePassage(source="refunds.md", ordinal=1, text="5 days", score=0.9)
        ],
        "reply": Reply(
            text="Refunds take 5 days. [1]",
            citations=[Citation(source="refunds.md", ordinal=1, quotes=["5 days"])],
        ),
    }

    assert (
        CHECKPOINT_SERDE.loads_typed(CHECKPOINT_SERDE.dumps_typed(request)) == request
    )


def test_search_and_reply_survive_the_serializer():
    """Equal only if the tuples load back as tuples, not as lists."""
    result = RetrievalResult(
        passages=(
            KnowledgePassage(source="refunds.md", ordinal=1, text="5 days", score=0.9),
        ),
        weak=(
            KnowledgePassage(source="shipping.md", ordinal=2, text="2 days", score=0.3),
        ),
        min_score=0.5,
    )
    state = {
        "ticket": Ticket(id="T-1", text="x"),
        "search": Search(queries=("refund",), result=result, ok=True),
        "reply": Reply(
            text="Refunds take 5 days. [1]",
            citations=[Citation(source="refunds.md", ordinal=1, quotes=["5 days"])],
        ),
    }

    assert CHECKPOINT_SERDE.loads_typed(CHECKPOINT_SERDE.dumps_typed(state)) == state
