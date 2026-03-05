# app/models.py
"""
Shared Pydantic models that mirror the data contracts
already used by the SvelteKit frontend (data.js / +server.js).
"""
from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field


# ── Inbound ticket context (what the frontend sends) ──────────────────────

class CustomerContext(BaseModel):
    name: str
    email: str
    tier: Literal["Bronze", "Silver", "Gold", "Platinum"]
    ltv: str               # e.g. "$2,840"
    orders: int            # total returns on record


class ItemContext(BaseModel):
    name: str
    category: str
    cls: str = Field("", alias="class")   # 'class' is a Python keyword
    price: str             # e.g. "149.99"
    return_qty: int = Field(1, alias="returnQty")

    model_config = {"populate_by_name": True}


class AnalyzeTicketRequest(BaseModel):
    """
    Payload the SvelteKit frontend POSTs when the agent clicks
    the '✦ AI Analyze' button.
    """
    ticket_id: str                          # e.g. "TKT-12345"
    return_reason: str = Field(..., alias="returnReason")
    return_amt: str   = Field(..., alias="returnAmt")   # string, e.g. "234.50"
    net_loss: str     = Field(..., alias="netLoss")
    customer: CustomerContext
    item: ItemContext

    model_config = {"populate_by_name": True}


# ── Outbound triage result (what the frontend renders) ────────────────────

class RefundSignal(BaseModel):
    type: Literal["full", "partial", "bulk"]
    note: str


class TriageFlag(BaseModel):
    type: str
    label: str
    severity: Literal["low", "medium", "high", "critical"]


class TriageResult(BaseModel):
    action: str                   # e.g. "replacement", "refund", "retention_offer"
    action_label: str             = Field(..., alias="actionLabel")
    action_rationale: str         = Field(..., alias="actionRationale")
    refund_signal: RefundSignal   = Field(..., alias="refundSignal")
    policy_ref: str               = Field(..., alias="policyRef")
    flags: list[TriageFlag]
    priority_override: str | None = Field(None, alias="priorityOverride")

    model_config = {"populate_by_name": True}


class AnalyzeTicketResponse(BaseModel):
    ticket_id: str
    triage: TriageResult
    # Future fields land here as agents are wired in:
    # routing: RoutingResult | None = None
    # draft: DraftResult    | None = None
    # supervisor: SupervisorResult | None = None
