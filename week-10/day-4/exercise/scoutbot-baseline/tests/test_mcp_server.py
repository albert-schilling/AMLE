"""Week 10 Day 2: ScoutBot's own MCP server, tested fully offline.

No subprocess and no network. `build_server(kb=...)` takes an injected knowledge base, so `search_policy`
runs against a tiny in-test stub instead of downloading an embedding model - the same "inject the
collaborator that needs the network" trick the graph tests use. The server is then wired to a client with
the in-memory transport (via `in_memory_provider`), exercising the exact discover-and-call path a real
MCP host would, just without the process boundary.
"""
from mcp.server.fastmcp import FastMCP

from scoutbot.knowledge import Retrieved
from scoutbot.mcp_client import in_memory_provider
from scoutbot.mcp_server import build_server


class StubKB:
    """A stand-in for KnowledgeBase: a fixed list of hits, no embedder, no SQLite, no model."""

    def __init__(self, hits):
        self._hits = hits

    def search(self, query, *, k=3):
        return self._hits[:k]


HITS = [
    Retrieved(source="refunds", ordinal=0, text="refunds are issued within five business days", score=0.9123),
    Retrieved(source="shipping", ordinal=1, text="orders ship within two business days", score=0.4211),
]


def _provider(kb):
    return in_memory_provider(build_server(kb=kb))


def test_server_publishes_both_tools_with_schemas_from_type_hints():
    provider = _provider(StubKB(HITS))
    by_name = {s["name"]: s for s in provider.tool_schemas()}
    assert set(by_name) == {"search_policy", "look_up_customer"}

    # search_policy: query required string, k optional integer defaulting to 3 - all from the hints.
    sp = by_name["search_policy"]["input_schema"]
    assert sp["properties"]["query"]["type"] == "string"
    assert sp["properties"]["k"]["type"] == "integer"
    assert sp["properties"]["k"]["default"] == 3
    assert sp["required"] == ["query"]

    # look_up_customer: customer_id required string.
    lu = by_name["look_up_customer"]["input_schema"]
    assert lu["properties"]["customer_id"]["type"] == "string"
    assert lu["required"] == ["customer_id"]


def test_search_policy_returns_scored_passages_from_the_injected_kb():
    provider = _provider(StubKB(HITS))
    obs = provider.call("search_policy", {"query": "when is my money back?", "k": 2})
    # A list return arrives wrapped under "result".
    passages = obs["result"]
    assert [p["source"] for p in passages] == ["refunds", "shipping"]
    assert passages[0]["text"] == "refunds are issued within five business days"
    assert passages[0]["score"] == 0.9123  # rounded, surfaced for the caller to judge confidence


def test_search_policy_respects_k():
    provider = _provider(StubKB(HITS))
    obs = provider.call("search_policy", {"query": "refund", "k": 1})
    assert len(obs["result"]) == 1
    assert obs["result"][0]["source"] == "refunds"


def test_look_up_customer_publishes_the_real_capability():
    # No kb needed for this tool; it reads mock_customers.json exactly like the native tool.
    provider = _provider(StubKB(HITS))
    obs = provider.call("look_up_customer", {"customer_id": "1001"})
    assert obs["found"] is True
    assert obs["plan"] == "pro"


def test_look_up_customer_reports_unknown_ids_as_data():
    provider = _provider(StubKB(HITS))
    obs = provider.call("look_up_customer", {"customer_id": "does-not-exist"})
    assert obs == {"found": False, "customer_id": "does-not-exist"}


def test_the_published_lookup_matches_the_native_tool():
    # Publishing the capability over MCP did not change it: the server tool and the in-process function
    # return the same thing for the same id.
    from scoutbot.tools import look_up_customer as native_look_up

    provider = _provider(StubKB(HITS))
    served = provider.call("look_up_customer", {"customer_id": "1001"})
    assert served == native_look_up("1001")


def test_build_server_returns_a_fastmcp_instance():
    assert isinstance(build_server(kb=StubKB(HITS)), FastMCP)
