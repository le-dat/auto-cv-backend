from langgraph.graph import StateGraph, END
from app.agents.state import WorkflowState
from app.agents.nodes import (
    parse_node,
    validate_node,
    context_node,
    match_node,
    rewrite_node,
    format_node,
)


def build_workflow():
    g = StateGraph(WorkflowState)
    for name, fn in [
        ("parse", parse_node.run),
        ("validate", validate_node.run),
        ("context", context_node.run),
        ("match", match_node.run),
        ("rewrite", rewrite_node.run),
        ("format", format_node.run),
    ]:
        g.add_node(name, fn)
    g.set_entry_point("parse")
    g.add_edge("parse", "validate")
    g.add_conditional_edges(
        "validate",
        lambda s: "error" if s.get("error") else "context",
        {"context": "context", "error": END},
    )
    g.add_edge("context", "match")
    g.add_edge("match", "rewrite")
    g.add_edge("rewrite", "format")
    g.add_edge("format", END)
    return g.compile()


workflow = build_workflow()
