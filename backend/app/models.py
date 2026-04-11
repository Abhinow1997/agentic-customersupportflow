# app/models.py
"""
Shared Pydantic models that mirror the data contracts
already used by the SvelteKit frontend (data.js / +server.js).
"""
from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field


# ── Inbound ticket context (what the frontend sends to /api/analyze) ───────

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
    ticket_id: str
    return_reason: str = Field(..., alias="returnReason")
    return_amt: str   = Field(..., alias="returnAmt")
    net_loss: str     = Field(..., alias="netLoss")
    customer: CustomerContext
    item: ItemContext

    model_config = {"populate_by_name": True}


# ── Outbound triage result ────────────────────────────────────────────────

class RefundSignal(BaseModel):
    type: Literal["full", "partial", "bulk"]
    note: str


class TriageFlag(BaseModel):
    type: str
    label: str
    severity: Literal["low", "medium", "high", "critical"]


class TriageResult(BaseModel):
    action: str
    action_label: str             = Field(..., alias="actionLabel")
    action_rationale: str         = Field(..., alias="actionRationale")
    refund_signal: RefundSignal   = Field(..., alias="refundSignal")
    policy_ref: str               = Field(..., alias="policyRef")
    flags: list[TriageFlag]
    priority_override: str | None = Field(None, alias="priorityOverride")

    model_config = {"populate_by_name": True}


# ── Routing result ────────────────────────────────────────────────────────

class RoutingResult(BaseModel):
    primary_department: str       = Field(..., alias="primaryDepartment")
    priority: str
    escalation_flags: dict[str, bool] = Field(default_factory=dict, alias="escalationFlags")
    handling_instructions: str    = Field("", alias="handlingInstructions")
    estimated_resolution_time: str = Field("24h", alias="estimatedResolutionTime")

    model_config = {"populate_by_name": True}


# ── RAG citation ──────────────────────────────────────────────────────────

class RagCitation(BaseModel):
    claim: str
    source_doc: str     = Field(..., alias="sourceDoc")
    source_section: str = Field("", alias="sourceSection")
    source_url: str     = Field("", alias="sourceUrl")
    confidence: float   = 0.0

    model_config = {"populate_by_name": True}


# ── Response draft ────────────────────────────────────────────────────────

class ResponseDraft(BaseModel):
    draft_response: str       = Field(..., alias="draftResponse")
    tone_applied: str         = Field("standard", alias="toneApplied")
    issues_addressed: list[str] = Field(default_factory=list, alias="issuesAddressed")
    rag_citations: list[RagCitation] = Field(default_factory=list, alias="ragCitations")
    requires_escalation: bool = Field(False, alias="requiresEscalation")

    model_config = {"populate_by_name": True}


# ── Supervisor report ─────────────────────────────────────────────────────

class SupervisorFailure(BaseModel):
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    detail: str


class SupervisorReport(BaseModel):
    approved: bool
    recommendation: Literal["send", "revise", "escalate"]
    confidence_score: float     = Field(0.0, alias="confidenceScore")
    failures: list[SupervisorFailure] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ── Full pipeline response ────────────────────────────────────────────────

class AnalyzeTicketResponse(BaseModel):
    ticket_id: str
    triage: TriageResult
    routing: RoutingResult | None = None
    rag_citations: list[RagCitation] = Field(default_factory=list, alias="ragCitations")
    response: ResponseDraft | None = None
    supervisor: SupervisorReport | None = None

    model_config = {"populate_by_name": True}


# ═══════════════════════════════════════════════════════════════════════════
# Tickets — GET /api/tickets, PATCH /api/tickets, POST /api/tickets/create
# ═══════════════════════════════════════════════════════════════════════════

class TicketItemModel(BaseModel):
    name: str
    category: str
    category_full: str = ""
    cls: str = Field("", alias="class")
    brand: str = ""
    price: str = "0.00"
    list_price: str = Field("0.00", alias="listPrice")
    desc: str = ""
    url: str = ""
    return_qty: int = Field(1, alias="returnQty")

    model_config = {"populate_by_name": True}


class TicketCustomerModel(BaseModel):
    name: str
    email: str
    tier: str = "Bronze"
    ltv: str = "0"
    orders: int = 0


class TicketTriageModel(BaseModel):
    action: str = ""
    action_label: str = Field("", alias="actionLabel")
    action_rationale: str = Field("", alias="actionRationale")
    refund_signal: dict = Field(default_factory=dict, alias="refundSignal")
    policy_ref: str = Field("", alias="policyRef")
    flags: list = Field(default_factory=list)
    priority_override: str | None = Field(None, alias="priorityOverride")

    model_config = {"populate_by_name": True}


class TicketResponse(BaseModel):
    id: str
    return_amt: str = Field("0.00", alias="returnAmt")
    net_loss: str   = Field("0.00", alias="netLoss")
    fee: str = "0.00"
    return_reason: str = Field("", alias="returnReason")
    customer: TicketCustomerModel
    item: TicketItemModel
    subject: str = ""
    preview: str = ""
    channel: str = "email"
    created: str = ""
    updated: str = ""
    status: str = "Open"
    resolution: str | None = None
    priority: str = "medium"
    triage: TicketTriageModel
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    urgency: int = 1
    department: str = "fulfillment"
    issues: list = Field(default_factory=list)
    escalation_signals: list = Field(default_factory=list)
    ai_draft: Any = None
    ai_citations: list = Field(default_factory=list)
    supervisor: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class TicketListResponse(BaseModel):
    tickets: list[TicketResponse]
    total: int


class UpdateTicketRequest(BaseModel):
    id: str
    status: Literal["Open", "Closed"]
    resolution: str | None = None


class UpdateTicketResponse(BaseModel):
    ok: bool
    id: str
    status: str
    resolution: str | None = None


# ── Create ticket ─────────────────────────────────────────────────────────

class CreateTicketItemInput(BaseModel):
    name: str
    category: str
    cls: str = Field("", alias="class")
    brand: str = ""
    price: str = "0"
    return_qty: int = Field(1, alias="returnQty")
    # sk  = actual I_ITEM_SK from the ITEM table
    # rn  = ROW_NUMBER() rank — what gets stored in SR_ITEM_SK
    sk: int | None = None
    rn: int | None = None

    model_config = {"populate_by_name": True}


class CreateTicketCustomerInput(BaseModel):
    name: str
    email: str
    tier: str = "Bronze"
    sk: int | None = None


class CreateTicketRequest(BaseModel):
    ticket_type: str = Field("return", alias="ticketType")
    customer: CreateTicketCustomerInput
    channel: str = "email"
    priority: str = "medium"
    complaint_desc: str = Field("", alias="complaintDesc")
    # packaging assessment
    packaging_condition: str = Field("", alias="packagingCondition")
    packaging_factor: float = Field(0.0, alias="packagingFactor")
    # return-specific
    item: CreateTicketItemInput | None = None
    reason_sk: int | None = Field(None, alias="reasonSk")
    reason_desc: str = Field("", alias="reasonDesc")
    return_amt: float = Field(0.0, alias="returnAmt")
    net_loss: float = Field(0.0, alias="netLoss")
    # enquiry-specific
    enquiry_subject: str = Field("", alias="enquirySubject")
    enquiry_category: str = Field("", alias="enquiryCategory")

    model_config = {"populate_by_name": True}


class CreateTicketResponse(BaseModel):
    ok: bool
    ticket_id: str = Field(..., alias="ticketId")
    ticket_number: str = Field(..., alias="ticketNumber")
    message: str
    demo: bool = False

    model_config = {"populate_by_name": True}


# ═══════════════════════════════════════════════════════════════════════════
# Reasons — GET /api/reasons
# ═══════════════════════════════════════════════════════════════════════════

class ReasonModel(BaseModel):
    id: int
    code: str
    desc: str


class ReasonsResponse(BaseModel):
    reasons: list[ReasonModel]


# ═══════════════════════════════════════════════════════════════════════════
# Customers — GET /api/customers
# ═══════════════════════════════════════════════════════════════════════════

class CustomerLookupResult(BaseModel):
    sk: int
    first_name: str = Field("", alias="firstName")
    last_name: str  = Field("", alias="lastName")
    name: str
    email: str
    preferred: bool
    tier: str

    model_config = {"populate_by_name": True}


class CustomerLookupResponse(BaseModel):
    found: bool
    customer: CustomerLookupResult | None = None
