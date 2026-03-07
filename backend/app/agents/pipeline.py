# app/agents/pipeline.py
"""
LangGraph pipeline -- wires all agent nodes together.

Full graph:
  [triage_node] -> [routing_node] -> [rag_node] -> [response_node] -> [supervisor_node] -> END

All node names use the _node suffix to avoid colliding with FlowState
keys (LangGraph forbids node names that match state TypedDict fields).
"""
from __future__ import annotations
from langgraph.graph import StateGraph, END

from app.agents.state import FlowState
from app.agents.triage_agent import triage_node
from app.agents.routing_agent import routing_node
from app.agents.rag_node import rag_retrieval_node
from app.agents.response_agent import response_node
from app.agents.supervisor_agent import supervisor_node


def build_pipeline() -> StateGraph:
    """
    Construct and compile the support-flow LangGraph state machine.
    Returns a compiled graph ready to invoke with an initial FlowState.
    """
    graph = StateGraph(FlowState)

    # ── Register nodes ────────────────────────────────────────────────────
    graph.add_node("triage_node",     triage_node)
    graph.add_node("routing_node",    routing_node)
    graph.add_node("rag_node",        rag_retrieval_node)
    graph.add_node("response_node",   response_node)
    graph.add_node("supervisor_node", supervisor_node)

    # ── Define edges ──────────────────────────────────────────────────────
    graph.set_entry_point("triage_node")
    graph.add_edge("triage_node",     "routing_node")
    graph.add_edge("routing_node",    "rag_node")
    graph.add_edge("rag_node",        "response_node")
    graph.add_edge("response_node",   "supervisor_node")
    graph.add_edge("supervisor_node", END)

    return graph.compile()


# Module-level singleton -- compiled once on import, reused across requests
pipeline = build_pipeline()
