# app/routers/analyze.py
"""
POST /api/analyze/ticket

Called by the SvelteKit frontend when the agent clicks the '✦ AI Analyze'
button on a ticket.  Runs the ticket through the LangGraph support-flow
pipeline and returns the triage result.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from app.models import AnalyzeTicketRequest, AnalyzeTicketResponse, TriageResult
from app.agents.pipeline import pipeline

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.post(
    "/ticket",
    response_model=AnalyzeTicketResponse,
    summary="Run AI triage on a support ticket",
    description=(
        "Accepts a ticket's context (return reason, item, customer) and runs it "
        "through the LangGraph multi-agent pipeline. "
        "Currently returns triage analysis only; routing, draft, and supervisor "
        "outputs will be added in subsequent iterations."
    ),
)
async def analyze_ticket(payload: AnalyzeTicketRequest) -> AnalyzeTicketResponse:
    # ── Build initial LangGraph state from the request ───────────────────
    initial_state = {
        "ticket_id":    payload.ticket_id,
        "return_reason": payload.return_reason,
        "return_amt":   float(payload.return_amt),
        "net_loss":     float(payload.net_loss),
        "customer_ctx": {
            "name":   payload.customer.name,
            "email":  payload.customer.email,
            "tier":   payload.customer.tier,
            "ltv":    payload.customer.ltv,
            "orders": payload.customer.orders,
        },
        "item_ctx": {
            "name":       payload.item.name,
            "category":   payload.item.category,
            "class":      payload.item.cls,
            "price":      payload.item.price,
            "return_qty": payload.item.return_qty,
        },
    }

    # ── Invoke the pipeline ───────────────────────────────────────────────
    try:
        result_state = await pipeline.ainvoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    # ── Surface pipeline-level errors ────────────────────────────────────
    if result_state.get("error"):
        raise HTTPException(status_code=500, detail=result_state["error"])

    triage_raw = result_state.get("triage")
    if not triage_raw:
        raise HTTPException(status_code=500, detail="Triage agent returned empty result")

    # ── Map raw triage dict → validated Pydantic model ───────────────────
    try:
        triage = TriageResult.model_validate(triage_raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Triage schema error: {exc}") from exc

    return AnalyzeTicketResponse(
        ticket_id=payload.ticket_id,
        triage=triage,
    )
