# app/routers/analyze.py
"""
POST /api/analyze/ticket

Called by the SvelteKit frontend when the agent clicks the 'AI Analyze'
button on a ticket.  Runs the ticket through the full LangGraph pipeline:

  triage -> routing -> RAG retrieval -> response draft -> supervisor

Returns the complete pipeline output.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException

from app.models import (
    AnalyzeTicketRequest, AnalyzeTicketResponse,
    TriageResult, RoutingResult, RagCitation,
    ResponseDraft, SupervisorReport,
)
from app.agents.pipeline import pipeline

logger = logging.getLogger("routers.analyze")

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.post(
    "/ticket",
    response_model=AnalyzeTicketResponse,
    summary="Run full AI pipeline on a support ticket",
    description=(
        "Accepts a ticket's context (return reason, item, customer) and runs it "
        "through the LangGraph multi-agent pipeline: "
        "triage -> routing -> RAG retrieval -> response draft -> supervisor."
    ),
)
async def analyze_ticket(payload: AnalyzeTicketRequest) -> AnalyzeTicketResponse:
    # ── Build initial LangGraph state from the request ───────────────────
    initial_state = {
        "ticket_id":     payload.ticket_id,
        "return_reason": payload.return_reason,
        "return_amt":    float(payload.return_amt),
        "net_loss":      float(payload.net_loss),
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

    # ── Invoke the full pipeline ──────────────────────────────────────────
    try:
        logger.info("=" * 60)
        logger.info("PIPELINE START: %s", payload.ticket_id)
        logger.info("  Customer: %s (%s)", payload.customer.name, payload.customer.tier)
        logger.info("  Item: %s [%s]", payload.item.name, payload.item.category)
        logger.info("  Reason: %s", payload.return_reason)
        logger.info("=" * 60)

        result_state = await pipeline.ainvoke(initial_state)
    except Exception as exc:
        logger.error("Pipeline error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    # ── Surface pipeline-level errors (non-fatal) ────────────────────────
    pipeline_error = result_state.get("error")
    if pipeline_error:
        logger.warning("Pipeline warning: %s", pipeline_error)

    # ── Log full pipeline results for visibility ─────────────────────────
    triage_raw = result_state.get("triage", {})
    routing_raw = result_state.get("routing", {})
    rag_raw = result_state.get("rag_results", [])
    response_raw = result_state.get("response", {})
    supervisor_raw = result_state.get("supervisor_report", {})

    logger.info("")
    logger.info("--- [1] TRIAGE ---")
    logger.info("  Action: %s (%s)", triage_raw.get("action"), triage_raw.get("actionLabel"))
    logger.info("  Rationale: %s", triage_raw.get("actionRationale", "")[:120])
    logger.info("  Policy: %s", triage_raw.get("policyRef", "")[:80])
    logger.info("  Flags: %s", [f.get("label") for f in triage_raw.get("flags", [])])

    logger.info("")
    logger.info("--- [2] ROUTING ---")
    logger.info("  Department: %s", routing_raw.get("primary_department"))
    logger.info("  Priority: %s", routing_raw.get("priority"))
    logger.info("  SLA: %s", routing_raw.get("estimated_resolution_time"))
    logger.info("  Escalation: %s", routing_raw.get("escalation_flags", {}))
    logger.info("  Instructions: %s", routing_raw.get("handling_instructions", "")[:120])

    logger.info("")
    logger.info("--- [3] RAG RETRIEVAL (ChromaDB) ---")
    if rag_raw:
        for i, r in enumerate(rag_raw, 1):
            logger.info("  [%d] %.3f | %s > %s",
                        i, r.get("confidence", 0),
                        r.get("source_doc", "?"),
                        r.get("source_section", "?"))
            logger.info("       %s", r.get("claim", "")[:100])
    else:
        logger.info("  (no citations retrieved)")

    logger.info("")
    logger.info("--- [4] RESPONSE DRAFT ---")
    logger.info("  Tone: %s", response_raw.get("tone_applied"))
    logger.info("  Issues addressed: %s", response_raw.get("issues_addressed", []))
    logger.info("  Citations used: %d", len(response_raw.get("rag_citations", [])))
    draft = response_raw.get("draft_response", "")
    logger.info("  Draft (first 200 chars): %s", draft[:200] if draft else "(none)")

    logger.info("")
    logger.info("--- [5] SUPERVISOR ---")
    logger.info("  Approved: %s", supervisor_raw.get("approved"))
    logger.info("  Recommendation: %s", supervisor_raw.get("recommendation"))
    logger.info("  Confidence: %s", supervisor_raw.get("confidence_score"))
    logger.info("  Failures: %s", [f.get("type") for f in supervisor_raw.get("failures", [])])
    logger.info("=" * 60)

    # ── Validate triage (required) ────────────────────────────────────────
    triage_raw = result_state.get("triage")
    if not triage_raw:
        raise HTTPException(status_code=500, detail="Triage agent returned empty result")

    try:
        triage = TriageResult.model_validate(triage_raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Triage schema error: {exc}") from exc

    # ── Validate routing (optional -- graceful fallback) ──────────────────
    routing = None
    routing_raw = result_state.get("routing")
    if routing_raw:
        try:
            routing = RoutingResult.model_validate(routing_raw)
        except Exception as exc:
            logger.warning("Routing validation failed: %s", exc)

    # ── Validate RAG citations (optional) ─────────────────────────────────
    rag_citations = []
    rag_raw = result_state.get("rag_results", [])
    for r in rag_raw:
        try:
            rag_citations.append(RagCitation.model_validate(r))
        except Exception:
            pass  # skip malformed citations

    # ── Validate response draft (optional) ────────────────────────────────
    response_draft = None
    response_raw = result_state.get("response")
    if response_raw:
        try:
            response_draft = ResponseDraft.model_validate(response_raw)
        except Exception as exc:
            logger.warning("Response validation failed: %s", exc)

    # ── Validate supervisor report (optional) ─────────────────────────────
    supervisor = None
    supervisor_raw = result_state.get("supervisor_report")
    if supervisor_raw:
        try:
            supervisor = SupervisorReport.model_validate(supervisor_raw)
        except Exception as exc:
            logger.warning("Supervisor validation failed: %s", exc)

    return AnalyzeTicketResponse(
        ticket_id=payload.ticket_id,
        triage=triage,
        routing=routing,
        rag_citations=rag_citations,
        response=response_draft,
        supervisor=supervisor,
    )
