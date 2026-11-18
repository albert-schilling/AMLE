from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ticket_classifier.models import (
    TriageState,
)
from ticket_classifier.nodes import (
    node_get_customer,
    node_mark_handled,
    node_wait_for_human,
    route_after_triage,
)
from ticket_classifier.triage_node import node_triage


def build_workflow(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Wire the nodes and compile. A checkpointer makes the runs resumable."""
    builder = StateGraph(TriageState)

    builder.add_node("node_get_customer", node_get_customer)
    builder.add_node("node_triage", node_triage)
    builder.add_node("node_wait_for_human", node_wait_for_human)
    builder.add_node("node_mark_handled", node_mark_handled)

    builder.add_edge(START, "node_get_customer")
    builder.add_edge("node_get_customer", "node_triage")
    builder.add_conditional_edges(
        "node_triage",
        route_after_triage,
        {
            "node_wait_for_human": "node_wait_for_human",
            "node_mark_handled": "node_mark_handled",
        },
    )
    builder.add_edge("node_wait_for_human", END)
    builder.add_edge("node_mark_handled", END)

    return builder.compile(checkpointer=checkpointer)


def write_mermaid(workflow: CompiledStateGraph, path: Path) -> None:
    """Save the graph as a mermaid diagram."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow.get_graph().draw_mermaid(), encoding="utf-8")
