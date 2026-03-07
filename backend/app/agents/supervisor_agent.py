# app/agents/supervisor_agent.py
"""
Supervisor Agent -- LangGraph node that validates the response draft.

The core architectural differentiator from single-prompt systems.
Checks for:
  1. ISSUE_DROPOUT   -- triage identified issues not addressed in draft
  2. UNGROUNDED_CLAIM -- claims in draft not backed by RAG citations
  3. MISSED_ESCALATION -- escalation flags from routing not actioned
  4. TONE_MISMATCH    -- response tone doesn't match customer tier/sentiment

Rule-based (no LLM call) for speed and determinism.
"""
from __future__ import annotations

import logging
from app.agents.state import FlowState

logger = logging.getLogger("agents.supervisor")


def supervisor_node(state: FlowState) -> FlowState:
    """
    LangGraph node: validate the response before it reaches human review.
    """
    try:
        triage   = state.get("triage", {})
        routing  = state.get("routing", {})
        response = state.get("response", {})
        rag      = state.get("rag_results", [])
        cust     = state.get("customer_ctx", {})

        failures: list[dict] = []
        draft = response.get("draft_response", "")

        # ── 1. Issue dropout check ────────────────────────────────────
        action = triage.get("action", "")
        addressed = response.get("issues_addressed", [])
        if action and action not in addressed:
            failures.append({
                "type": "ISSUE_DROPOUT",
                "severity": "high",
                "detail": f"Triage action '{action}' not in issues_addressed: {addressed}",
            })

        # ── 2. Grounding check ────────────────────────────────────────
        rag_citations = response.get("rag_citations", [])
        if rag and not rag_citations:
            failures.append({
                "type": "UNGROUNDED_CLAIM",
                "severity": "medium",
                "detail": "RAG provided citations but response used none.",
            })

        # ── 3. Escalation check ───────────────────────────────────────
        esc_flags = routing.get("escalation_flags", {})
        requires_esc = response.get("requires_escalation", False)

        if esc_flags.get("manager_review") and not requires_esc:
            failures.append({
                "type": "MISSED_ESCALATION",
                "severity": "critical",
                "detail": "Routing requires manager review but response doesn't flag escalation.",
            })

        if esc_flags.get("compliance_alert") and not requires_esc:
            failures.append({
                "type": "MISSED_ESCALATION",
                "severity": "critical",
                "detail": "Compliance alert active but response doesn't flag escalation.",
            })

        # ── 4. Tone check ────────────────────────────────────────────
        tier = cust.get("tier", "Bronze")
        tone = response.get("tone_applied", "standard")

        if tier in ("Gold", "Platinum") and tone == "standard":
            failures.append({
                "type": "TONE_MISMATCH",
                "severity": "low",
                "detail": f"{tier} customer but standard tone applied (expected premium/empathetic).",
            })

        # ── 5. Empty draft check ─────────────────────────────────────
        if not draft or len(draft) < 50:
            failures.append({
                "type": "EMPTY_DRAFT",
                "severity": "critical",
                "detail": "Draft response is empty or too short.",
            })

        # ── Score & recommendation ────────────────────────────────────
        critical_count = sum(1 for f in failures if f["severity"] == "critical")
        high_count     = sum(1 for f in failures if f["severity"] == "high")

        if critical_count > 0:
            recommendation = "escalate"
            confidence = 0.3
        elif high_count > 0:
            recommendation = "revise"
            confidence = 0.55
        elif failures:
            recommendation = "revise"
            confidence = 0.7
        else:
            recommendation = "send"
            confidence = 0.9 + (0.05 if rag_citations else 0)

        # Clamp
        confidence = min(confidence, 0.99)

        supervisor_report = {
            "approved":         len(failures) == 0,
            "recommendation":   recommendation,
            "confidence_score":  round(confidence, 2),
            "failures":         failures,
        }

        logger.info(
            "Supervisor: %s (confidence=%.2f, failures=%d)",
            recommendation, confidence, len(failures),
        )

        return {**state, "supervisor_report": supervisor_report}

    except Exception as exc:
        logger.error("Supervisor failed: %s", exc)
        return {
            **state,
            "supervisor_report": {
                "approved": False,
                "recommendation": "revise",
                "confidence_score": 0.0,
                "failures": [{"type": "SUPERVISOR_ERROR", "severity": "critical", "detail": str(exc)}],
            },
        }
