from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .context import WorkflowContext
from .models import TriageState
from .nodes import (
    node_get_customer,
    node_human_review,
    node_mark_handled,
    node_retrieve_knowledge,
    node_triage,
    route_after_triage,
)
from .nodes.names import (
    GET_CUSTOMER,
    HUMAN_REVIEW,
    MARK_HANDLED,
    RETRIEVE_KNOWLEDGE,
    TRIAGE,
)

# State, runtime context, input and output types of the compiled graph.
Workflow = CompiledStateGraph[TriageState, WorkflowContext, TriageState, TriageState]


def build_workflow(
    checkpointer: BaseCheckpointSaver[str] | None = None,
) -> Workflow:
    """Wire the nodes and compile. A checkpointer makes the runs resumable.

    Runs that reach ``retrieve_knowledge`` need a ``WorkflowContext``.
    """
    builder = StateGraph(TriageState, context_schema=WorkflowContext)

    builder.add_node(GET_CUSTOMER, node_get_customer)
    builder.add_node(RETRIEVE_KNOWLEDGE, node_retrieve_knowledge)
    builder.add_node(TRIAGE, node_triage)
    builder.add_node(HUMAN_REVIEW, node_human_review)
    builder.add_node(MARK_HANDLED, node_mark_handled)

    builder.add_edge(START, GET_CUSTOMER)
    builder.add_edge(GET_CUSTOMER, RETRIEVE_KNOWLEDGE)
    builder.add_edge(RETRIEVE_KNOWLEDGE, TRIAGE)
    builder.add_conditional_edges(TRIAGE, route_after_triage)
    builder.add_edge(HUMAN_REVIEW, END)
    builder.add_edge(MARK_HANDLED, END)

    return builder.compile(checkpointer=checkpointer)


def write_mermaid(workflow: Workflow, path: Path) -> None:
    """Save the graph as a mermaid diagram."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow.get_graph().draw_mermaid(), encoding="utf-8")
