from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .models import TriageState
from .nodes import (
    node_get_customer,
    node_human_review,
    node_mark_handled,
    node_triage,
    route_after_triage,
)
from .nodes.names import GET_CUSTOMER, HUMAN_REVIEW, MARK_HANDLED, TRIAGE


def build_workflow(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Wire the nodes and compile. A checkpointer makes the runs resumable."""
    builder = StateGraph(TriageState)

    builder.add_node(GET_CUSTOMER, node_get_customer)
    builder.add_node(TRIAGE, node_triage)
    builder.add_node(HUMAN_REVIEW, node_human_review)
    builder.add_node(MARK_HANDLED, node_mark_handled)

    builder.add_edge(START, GET_CUSTOMER)
    builder.add_edge(GET_CUSTOMER, TRIAGE)
    builder.add_conditional_edges(TRIAGE, route_after_triage)
    builder.add_edge(HUMAN_REVIEW, END)
    builder.add_edge(MARK_HANDLED, END)

    return builder.compile(checkpointer=checkpointer)


def write_mermaid(workflow: CompiledStateGraph, path: Path) -> None:
    """Save the graph as a mermaid diagram."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow.get_graph().draw_mermaid(), encoding="utf-8")
