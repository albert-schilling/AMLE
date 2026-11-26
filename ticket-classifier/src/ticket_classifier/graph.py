from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .context import WorkflowContext
from .models import TriageState
from .nodes import (
    node_critique_retrieval,
    node_draft_reply,
    node_formulate_query,
    node_get_customer,
    node_human_review,
    node_mark_handled,
    node_retrieve_knowledge,
    node_triage,
    route_after_critique,
    route_by_priority,
)
from .nodes.names import (
    CRITIQUE_RETRIEVAL,
    DRAFT_REPLY,
    FORMULATE_QUERY,
    GET_CUSTOMER,
    HUMAN_REVIEW,
    MARK_HANDLED,
    REFORMULATE,
    RETRIEVE_KNOWLEDGE,
    SEARCH_DONE,
    TRIAGE,
)

# State, runtime context, input and output types of the compiled graph.
Workflow = CompiledStateGraph[TriageState, WorkflowContext, TriageState, TriageState]


def build_workflow(
    checkpointer: BaseCheckpointSaver[str] | None = None,
) -> Workflow:
    """Wire the nodes and compile. A checkpointer makes the runs resumable.

    Runs that reach the knowledge search need a ``WorkflowContext``.
    """
    builder = StateGraph(TriageState, context_schema=WorkflowContext)

    builder.add_node(GET_CUSTOMER, node_get_customer)
    builder.add_node(FORMULATE_QUERY, node_formulate_query)
    builder.add_node(RETRIEVE_KNOWLEDGE, node_retrieve_knowledge)
    builder.add_node(CRITIQUE_RETRIEVAL, node_critique_retrieval)
    builder.add_node(TRIAGE, node_triage)
    builder.add_node(DRAFT_REPLY, node_draft_reply)
    builder.add_node(HUMAN_REVIEW, node_human_review)
    builder.add_node(MARK_HANDLED, node_mark_handled)

    builder.add_edge(START, GET_CUSTOMER)
    builder.add_edge(GET_CUSTOMER, FORMULATE_QUERY)
    builder.add_edge(FORMULATE_QUERY, RETRIEVE_KNOWLEDGE)
    builder.add_edge(RETRIEVE_KNOWLEDGE, CRITIQUE_RETRIEVAL)
    # The only cycle: a weak search goes back for a reworded query.
    builder.add_conditional_edges(
        CRITIQUE_RETRIEVAL,
        route_after_critique,
        {REFORMULATE: FORMULATE_QUERY, SEARCH_DONE: TRIAGE},
    )
    builder.add_edge(TRIAGE, DRAFT_REPLY)
    builder.add_conditional_edges(DRAFT_REPLY, route_by_priority)
    builder.add_edge(HUMAN_REVIEW, END)
    builder.add_edge(MARK_HANDLED, END)

    return builder.compile(checkpointer=checkpointer)


def write_mermaid(workflow: Workflow, path: Path) -> None:
    """Save the graph as a mermaid diagram."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow.get_graph().draw_mermaid(), encoding="utf-8")
