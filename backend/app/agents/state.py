# app/agents/state.py
"""
LangGraph shared state contract.
Every node in the pipeline reads from and writes to this TypedDict.
Mirrors the FlowState design documented in technical-version.md.
"""
from __future__ import annotations
from typing import TypedDict, Any


class FlowState(TypedDict, total=False):
    # ── Input ──────────────────────────────────────────────────────────────
    ticket_id: str
    return_reason: str
    return_amt: float
    net_loss: float
    customer_ctx: dict[str, Any]   # name, email, tier, ltv, orders
    item_ctx: dict[str, Any]       # name, category, class, price, return_qty

    # ── Agent outputs (populated as pipeline runs) ─────────────────────────
    triage: dict[str, Any]         # TriageAgent output
    routing: dict[str, Any]        # RoutingAgent output  (future)
    rag_results: list[dict]        # RAG retrieval        (future)
    response: dict[str, Any]       # ResponseAgent output (future)
    supervisor_report: dict[str, Any]  # SupervisorAgent  (future)

    # ── Pipeline control ───────────────────────────────────────────────────
    error: str | None
