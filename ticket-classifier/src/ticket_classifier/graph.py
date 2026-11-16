from langgraph.graph import END, START, StateGraph

from ticket_classifier.models import (
    TriageState,
)
from ticket_classifier.nodes import node_get_customer
from ticket_classifier.triage_node import node_triage

graph = StateGraph(TriageState)

graph.add_node("node_get_customer", node_get_customer)
graph.add_node("node_triage", node_triage)

graph.add_edge(START, "node_get_customer")
graph.add_edge("node_get_customer", "node_triage")
graph.add_edge("node_triage", END)

workflow = graph.compile()

# Save mermaid to file to output/graph.mmd
with open("output/graph.mmd", "w") as f:
    f.write(workflow.get_graph().draw_mermaid())
