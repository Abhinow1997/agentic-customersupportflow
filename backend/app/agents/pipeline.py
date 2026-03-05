# app/agents/pipeline.py
"""
LangGraph pipeline — wires all agent nodes together.

Current graph:  [triage_node]
Planned graph:  [triage_node] → [routing_node] → [response_node] → [supervisor_node]
"""
from __future__ import annotations
from langgraph.graph import StateGraph, END

from app.agents.state import FlowState
from app.agents.triage_agent import triage_node


def build_pipeline() -> StateGraph:
    """
    Construct and compile the support-flow LangGraph state machine.
    Returns a compiled graph ready to invoke with an initial FlowState.
    """
    graph = StateGraph(FlowState)

    # ── Register nodes ────────────────────────────────────────────────────
    # Node names use _node suffix to avoid colliding with FlowState keys
    # (LangGraph forbids node names that match state TypedDict fields)
    graph.add_node("triage_node", triage_node)

    # Placeholder stubs — will be replaced with real nodes in next iterations
    # graph.add_node("routing_node",    routing_node)
    # graph.add_node("response_node",   response_node)
    # graph.add_node("supervisor_node", supervisor_node)

    # ── Define edges ──────────────────────────────────────────────────────
    graph.set_entry_point("triage_node")
    graph.add_edge("triage_node", END)

    # Future edges:
    # graph.add_edge("triage_node",    "routing_node")
    # graph.add_edge("routing_node",   "response_node")
    # graph.add_edge("response_node",  "supervisor_node")
    # graph.add_edge("supervisor_node", END)

    return graph.compile()


# Module-level singleton — compiled once on import, reused across requests
pipeline = build_pipeline()
