# app/agents/routing_agent.py
"""
Routing Agent -- LangGraph node that decides ownership, SLA, and escalation.

Reads triage output and customer context to determine:
  - primary_department
  - priority (with possible override)
  - escalation_flags
  - handling_instructions
  - estimated_resolution_time

This is a rule-based node (no LLM call) -- fast and deterministic.
"""
from __future__ import annotations

import logging
from app.agents.state import FlowState

logger = logging.getLogger("agents.routing")


def routing_node(state: FlowState) -> FlowState:
    """
    LangGraph node: determine routing based on triage + customer context.
    """
    try:
        triage = state.get("triage", {})
        cust   = state.get("customer_ctx", {})
        item   = state.get("item_ctx", {})

        action    = triage.get("action", "refund")
        flags     = triage.get("flags", [])
        tier      = cust.get("tier", "Bronze")
        net_loss  = float(state.get("net_loss", 0) or 0)
        category  = item.get("category", "").lower()

        # ── Department assignment ─────────────────────────────────────
        if action in ("replacement", "replacement_escalate", "exchange_first"):
            department = "fulfillment"
        elif action in ("refund", "refund_or_reship"):
            department = "billing"
        elif action == "retention_offer":
            department = "retention"
        elif action == "escalate_quality":
            department = "quality"
        else:
            department = "general"

        # ── Priority ──────────────────────────────────────────────────
        priority = triage.get("priorityOverride")
        if not priority:
            if net_loss > 500:
                priority = "critical"
            elif net_loss > 200 or tier in ("Gold", "Platinum"):
                priority = "high"
            elif net_loss > 50:
                priority = "medium"
            else:
                priority = "low"

        # ── Escalation flags ──────────────────────────────────────────
        escalation_flags = {
            "manager_review":   any(f.get("severity") == "critical" for f in flags),
            "compliance_alert": action == "escalate_quality",
            "retention_risk":   tier in ("Gold", "Platinum") and action in ("refund", "retention_offer"),
        }

        # ── Handling instructions ─────────────────────────────────────
        instructions = []
        if escalation_flags["retention_risk"]:
            instructions.append(f"Retention priority: {tier} customer, offer credit before refund.")
        if escalation_flags["compliance_alert"]:
            instructions.append("Quality team review required before processing.")
        if action == "replacement_escalate":
            instructions.append("Replace item immediately AND flag for batch defect investigation.")
        if not instructions:
            instructions.append(f"Standard {action.replace('_', ' ')} workflow.")

        # ── SLA ───────────────────────────────────────────────────────
        sla_hours = {
            "critical": "4h", "high": "12h", "medium": "24h", "low": "48h"
        }.get(priority, "24h")

        routing = {
            "primary_department":       department,
            "priority":                 priority,
            "escalation_flags":         escalation_flags,
            "handling_instructions":    " ".join(instructions),
            "estimated_resolution_time": sla_hours,
        }

        logger.info(
            "Routed: dept=%s, priority=%s, SLA=%s",
            department, priority, sla_hours,
        )

        return {**state, "routing": routing}

    except Exception as exc:
        logger.error("Routing failed: %s", exc)
        return {
            **state,
            "routing": {
                "primary_department": "general",
                "priority": "medium",
                "escalation_flags": {},
                "handling_instructions": "Routing failed -- manual review required.",
                "estimated_resolution_time": "24h",
            },
            "error": f"Routing error: {exc}",
        }
