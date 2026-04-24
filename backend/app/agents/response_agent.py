# app/agents/response_agent.py
"""
Response Agent -- LangGraph node that drafts a grounded customer response.

Reads:
  - state["triage"]       (action, rationale, flags)
  - state["routing"]      (department, priority, instructions)
  - state["rag_results"]  (policy citations from ChromaDB)
  - state["customer_ctx"] (name, tier, ltv)
  - state["item_ctx"]     (product, category, price)

Writes:
  - state["response"]  { draft_response, tone_applied, issues_addressed,
                          rag_citations, requires_escalation }

Uses LiteLLM (same provider as triage_agent) to generate the draft,
but grounds it in the RAG policy citations.
"""
from __future__ import annotations

import json
import os
import re
import logging
import random
from datetime import datetime
from typing import Any

import litellm
from app.agents.state import FlowState
from app.config import get_settings
from app.db import run_query

logger = logging.getLogger("agents.response")
settings = get_settings()

LLM_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a customer support response writer for Walmart,
an e-commerce company. You draft professional, empathetic customer-facing
responses grounded in verified policy citations.

CRITICAL RULES:
1. ONLY cite policies from the "Policy Citations" section provided.
2. If evidence is missing for a claim, write "I will confirm that policy"
   -- NEVER invent policy details.
3. Reference the customer by first name.
4. Address ALL issues identified in the triage.
5. Match tone to customer tier: Bronze=friendly, Silver=attentive,
   Gold=premium, Platinum=white-glove.
6. Keep the response under 200 words.

You must respond with ONLY a valid JSON object:
{
  "draft_response": "<the customer-facing email text>",
  "tone_applied": "standard" or "empathetic" or "premium" or "urgent",
  "issues_addressed": ["<issue1>", "<issue2>"],
  "rag_citations": [
    {
      "claim": "<what you cited>",
      "source_doc": "<policy name>",
      "source_section": "<section>",
      "confidence": <0.0-1.0>
    }
  ],
  "requires_escalation": false
}
"""


def response_node(state: FlowState) -> FlowState:
    """
    LangGraph node: draft a grounded customer response.
    Falls back to a template if the LLM call fails.
    """
    try:
        brief = _build_brief(state)
        raw   = _call_llm(brief)
        resp  = _parse_response(raw)
        return {**state, "response": resp}
    except Exception as exc:
        logger.error("Response agent LLM failed: %s", exc)
        fallback = _template_fallback(state)
        return {**state, "response": fallback, "error": f"Response LLM failed ({exc}), used template"}


def _build_brief(state: FlowState) -> str:
    triage  = state.get("triage", {})
    routing = state.get("routing", {})
    cust    = state.get("customer_ctx", {})
    item    = state.get("item_ctx", {})
    rag     = state.get("rag_results", [])

    # Format RAG citations for the prompt
    citations_text = "No policy citations available."
    if rag:
        lines = []
        for i, r in enumerate(rag, 1):
            lines.append(
                f"  [{i}] {r.get('source_doc', '?')} > {r.get('source_section', '?')} "
                f"(conf: {r.get('confidence', 0):.2f})\n"
                f"      \"{r.get('claim', '')[:200]}\""
            )
        citations_text = "\n".join(lines)

    first_name = (cust.get("name", "Customer").split()[0])

    return f"""## Customer Response Brief

### Customer
- Name: {cust.get('name', 'Customer')} (first name: {first_name})
- Tier: {cust.get('tier', 'Bronze')}
- LTV: {cust.get('ltv', 'unknown')}

### Item
- Product: {item.get('name', 'Unknown')}
- Category: {item.get('category', 'General')}
- Price: ${item.get('price', '0')}

### Triage Decision
- Action: {triage.get('action', 'refund')}
- Label: {triage.get('actionLabel', '')}
- Rationale: {triage.get('actionRationale', '')}

### Routing
- Department: {routing.get('primary_department', 'general')}
- Priority: {routing.get('priority', 'medium')}
- Instructions: {routing.get('handling_instructions', '')}

### Return Context
- Reason: {state.get('return_reason', '')}
- Return Amount: ${state.get('return_amt', 0)}
- Net Loss: ${state.get('net_loss', 0)}

### Policy Citations (from RAG -- ONLY cite from these)
{citations_text}

Draft a customer response addressing all issues. Ground claims in the citations above."""


def _call_llm(brief: str) -> str:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    response = litellm.completion(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": brief},
        ],
        temperature=0.3,
        max_tokens=1000,
    )
    return response.choices[0].message.content.strip()


def _parse_response(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    data = json.loads(cleaned)

    required = {"draft_response", "tone_applied", "issues_addressed", "rag_citations"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Response missing keys: {missing}")

    data.setdefault("requires_escalation", False)
    return data


def _template_fallback(state: FlowState) -> dict:
    """Simple template when LLM is unavailable."""
    cust   = state.get("customer_ctx", {})
    item   = state.get("item_ctx", {})
    triage = state.get("triage", {})
    first  = (cust.get("name", "Customer").split()[0])
    action = triage.get("actionLabel", "process your return")

    draft = (
        f"Dear {first},\n\n"
        f"Thank you for reaching out regarding your {item.get('name', 'item')} return. "
        f"We will {action.lower()} as quickly as possible.\n\n"
        f"If you have any questions, please don't hesitate to reply.\n\n"
        f"Best regards,\n[Agent Name]\nArcella Customer Care"
    )

    return {
        "draft_response": draft,
        "tone_applied": "standard",
        "issues_addressed": [triage.get("action", "refund")],
        "rag_citations": [],
        "requires_escalation": False,
    }


# =============================================================================
# Enquiry workflow helpers
# =============================================================================

ENQUIRY_MAIN_CATEGORIES = [
    "Order & Delivery Enquiries",
    "Returns & Refunds Enquiries",
    "Billing & Payment Enquiries",
    "Account Management Enquiries",
    "General Enquiries",
]

ENQUIRY_SUBCATEGORIES = {
    "Order & Delivery Enquiries": [
        "Where is my order?",
        "Tracking not updating",
        "Delivery delay",
        "Missing package",
        "Wrong address / delivery issue",
    ],
    "Returns & Refunds Enquiries": [
        "Return status",
        "Refund pending",
        "Replacement request",
        "Return label / instructions",
        "Exchange request",
    ],
    "Billing & Payment Enquiries": [
        "Double charge",
        "Refund not received",
        "Card declined",
        "Invoice / receipt request",
        "Promo code / discount issue",
    ],
    "Account Management Enquiries": [
        "Password reset",
        "Login issue",
        "Email / phone update",
        "Account locked",
        "Profile changes",
    ],
    "General Enquiries": [
        "Product information",
        "Policy question",
        "Complaint / feedback",
        "Escalation request",
        "Other",
    ],
}

ENQUIRY_CATEGORY_KEYWORDS = {
    "Order & Delivery Enquiries": [
        "where is my order", "wismo", "tracking", "track", "shipping", "shipped",
        "delivery", "delivered", "late", "delay", "missing package", "not arrived",
        "in transit", "carrier",
    ],
    "Returns & Refunds Enquiries": [
        "return", "refund", "replacement", "exchange", "label", "return status",
        "refund pending", "refund not received",
    ],
    "Billing & Payment Enquiries": [
        "double charge", "charged twice", "billing", "payment", "invoice",
        "receipt", "card declined", "promo code", "discount", "payment failed",
    ],
    "Account Management Enquiries": [
        "password", "login", "sign in", "account locked", "email update",
        "phone update", "profile", "account access",
    ],
}


def analyze_enquiry_message(payload: dict[str, Any]) -> dict[str, Any]:
    customer = payload.get("customer", {}) or {}
    message = _join_message_parts(payload.get("subject", ""), payload.get("body", ""))

    classification = _classify_enquiry(message, customer, payload)
    ticket_context = _lookup_enquiry_ticket_context(
        customer.get("email") or payload.get("sender_email") or payload.get("senderEmail") or "",
    )
    procedure = _category_tool(classification["category"], message, customer, payload, ticket_context)
    draft = _draft_enquiry_email(message, customer, classification, procedure, ticket_context)

    suggestions = _apply_draft_to_suggestions(procedure["suggestions"], draft)

    analysis_id = f"ENQ-AN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"

    return {
        "analysis_id": analysis_id,
        "classification": {
            "category": classification["category"],
            "subcategory": classification["subcategory"],
            "confidence": classification["confidence"],
            "sentiment_label": classification["sentiment_label"],
            "sentiment_score": classification["sentiment_score"],
            "urgency_score": classification["urgency_score"],
            "priority": classification["priority"],
            "procedure_name": procedure["procedure_name"],
            "open_ticket_status": ticket_context["ticket_phrase"],
            "open_ticket_count": ticket_context["open_count"],
            "validation_questions": procedure["validation_questions"],
        },
        "draft_subject": draft["draft_subject"],
        "draft_response": draft["draft_response"],
        "ai_summary": draft["ai_summary"],
        "suggestions": suggestions,
        "procedure_notes": procedure["procedure_notes"],
        "ticket_context_note": ticket_context["note"],
    }


def _join_message_parts(subject: str, body: str) -> str:
    parts = [subject.strip(), body.strip()]
    return "\n\n".join(part for part in parts if part)


def _classify_enquiry(message: str, customer: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    text = f"{message} {customer.get('name', '')} {customer.get('email', '')}".lower()

    category = "General Enquiries"
    for candidate, keywords in ENQUIRY_CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            category = candidate
            break

    subcategory = _pick_subcategory(category, text)
    urgency_score = _score_urgency(text)
    sentiment_label, sentiment_score = _score_sentiment(text)
    confidence = 0.91 if category != "General Enquiries" else 0.73
    if urgency_score >= 4:
        confidence = min(0.97, confidence + 0.03)

    priority = _priority_from_scores(urgency_score, sentiment_score)

    return {
        "category": category,
        "subcategory": subcategory,
        "confidence": confidence,
        "sentiment_label": sentiment_label,
        "sentiment_score": sentiment_score,
        "urgency_score": urgency_score,
        "priority": priority,
    }


def _pick_subcategory(category: str, text: str) -> str:
    text = text.lower()
    if category == "Order & Delivery Enquiries":
        if any(k in text for k in ["where is my order", "wismo", "not arrived", "where is", "arrived yet"]):
            return "Where is my order?"
        if any(k in text for k in ["tracking", "not updating", "scan", "in transit"]):
            return "Tracking not updating"
        if any(k in text for k in ["late", "delay", "delayed"]):
            return "Delivery delay"
        if any(k in text for k in ["missing package", "lost", "did not receive", "not delivered"]):
            return "Missing package"
        if any(k in text for k in ["wrong address", "address", "delivery issue"]):
            return "Wrong address / delivery issue"
        return "Where is my order?"

    if category == "Returns & Refunds Enquiries":
        if "refund" in text and any(k in text for k in ["pending", "not received", "missing"]):
            return "Refund pending"
        if any(k in text for k in ["return status", "where is my return", "return update"]):
            return "Return status"
        if any(k in text for k in ["replacement", "replace"]):
            return "Replacement request"
        if any(k in text for k in ["label", "instructions", "how do i return"]):
            return "Return label / instructions"
        if any(k in text for k in ["exchange", "swap"]):
            return "Exchange request"
        return "Return status"

    if category == "Billing & Payment Enquiries":
        if any(k in text for k in ["double charge", "charged twice", "duplicate charge"]):
            return "Double charge"
        if any(k in text for k in ["refund not received", "refund pending", "refund missing"]):
            return "Refund not received"
        if any(k in text for k in ["declined", "card declined", "payment failed"]):
            return "Card declined"
        if any(k in text for k in ["invoice", "receipt", "statement"]):
            return "Invoice / receipt request"
        if any(k in text for k in ["promo code", "discount", "coupon"]):
            return "Promo code / discount issue"
        return "Invoice / receipt request"

    if category == "Account Management Enquiries":
        if any(k in text for k in ["password", "reset"]):
            return "Password reset"
        if any(k in text for k in ["login", "sign in", "log in"]):
            return "Login issue"
        if any(k in text for k in ["email update", "phone update", "change email", "change phone"]):
            return "Email / phone update"
        if any(k in text for k in ["locked", "account locked", "blocked"]):
            return "Account locked"
        if any(k in text for k in ["profile", "name change", "address change"]):
            return "Profile changes"
        return "Login issue"

    if any(k in text for k in ["complaint", "feedback", "issue"]):
        return "Complaint / feedback"
    if any(k in text for k in ["product", "pricing", "feature"]):
        return "Product information"
    return "Other"


def _score_urgency(text: str) -> int:
    urgent_hits = [
        "urgent", "asap", "immediately", "today", "right away",
        "lost", "stuck", "blocked", "not working", "not received",
        "where is my order", "late", "delay", "double charge",
    ]
    score = 1
    for hit in urgent_hits:
        if hit in text:
            score += 1
    return min(score, 5)


def _score_sentiment(text: str) -> tuple[str, float]:
    negative_hits = [
        "angry", "upset", "frustrated", "disappointed", "annoyed",
        "terrible", "awful", "bad", "late", "lost", "broken", "wrong",
    ]
    positive_hits = ["thanks", "thank you", "appreciate", "great", "helpful"]

    score = 0.0
    for hit in negative_hits:
        if hit in text:
            score -= 0.15
    for hit in positive_hits:
        if hit in text:
            score += 0.1

    score = max(-1.0, min(1.0, score))
    if score < -0.2:
        return "Negative", score
    if score > 0.2:
        return "Positive", score
    return "Neutral", score


def _priority_from_scores(urgency_score: int, sentiment_score: float) -> str:
    if urgency_score >= 5 or sentiment_score <= -0.5:
        return "Critical"
    if urgency_score >= 4:
        return "High"
    if urgency_score >= 3:
        return "Medium"
    return "Low"


def _lookup_enquiry_ticket_context(email: str) -> dict[str, Any]:
    if not email:
        return {
            "open_count": 0,
            "ticket_phrase": "no ticket filed",
            "note": "No customer email provided, so ticket presence could not be checked.",
        }

    try:
        rows = run_query(
            """
            SELECT ENQ_TICKET_NUMBER, ENQ_STATUS, ENQ_CATEGORY
            FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
            WHERE LOWER(ENQ_CUSTOMER_EMAIL) = LOWER(%s)
            ORDER BY ENQ_CREATED_AT DESC
            LIMIT 10
            """,
            (email,),
        )
        open_rows = [row for row in rows if str(row.get("ENQ_STATUS", "")).lower() == "open"]
        open_count = len(open_rows)
        if open_count:
            phrase = "an open ticket" if open_count == 1 else f"{open_count} open tickets"
            note = f"I see {phrase} in our system."
        else:
            phrase = "no ticket filed"
            note = "I do not see an open ticket in our system yet."
        return {
            "open_count": open_count,
            "ticket_phrase": phrase,
            "note": note,
        }
    except Exception as exc:
        logger.warning("Enquiry ticket context lookup failed: %s", exc)
        return {
            "open_count": 0,
            "ticket_phrase": "no ticket filed",
            "note": "Ticket presence could not be checked right now.",
        }


def _category_tool(
    category: str,
    message: str,
    customer: dict[str, Any],
    payload: dict[str, Any],
    ticket_context: dict[str, Any],
) -> dict[str, Any]:
    tool_map = {
        "Order & Delivery Enquiries": _order_delivery_tool,
        "Returns & Refunds Enquiries": _returns_refunds_tool,
        "Billing & Payment Enquiries": _billing_payment_tool,
        "Account Management Enquiries": _account_management_tool,
        "General Enquiries": _general_enquiry_tool,
    }
    tool = tool_map.get(category, _general_enquiry_tool)
    return tool(message, customer, payload, ticket_context)


def _base_suggestions(subject: str, response: str, summary: str, internal: str, next_step: str) -> list[dict[str, Any]]:
    return [
        {"id": "subject", "label": "Subject line", "text": subject, "selected": True},
        {"id": "response", "label": "Customer reply", "text": response, "selected": True},
        {"id": "summary", "label": "Internal summary", "text": summary, "selected": True},
        {"id": "next_step", "label": "Next step", "text": next_step, "selected": True},
        {"id": "internal_note", "label": "Internal note", "text": internal, "selected": False},
    ]


def _order_delivery_tool(
    message: str,
    customer: dict[str, Any],
    payload: dict[str, Any],
    ticket_context: dict[str, Any],
) -> dict[str, Any]:
    first = _first_name(customer.get("name") or payload.get("sender_name") or "Customer")
    subject = "Update on your order and delivery"
    response = (
        f"Hi {first},\n\n"
        "Thanks for reaching out. Your order was placed on [date] and shipped via [carrier/mode]. "
        "For real-time tracking, please check [carrier website]. "
        f"If there's an issue, I see {ticket_context['ticket_phrase']} in our system.\n\n"
        "If you can share the order number, I can narrow this down further.\n\n"
        "Best regards,\nArcella Customer Care"
    )
    summary = "Customer needs an order and delivery update; verify shipment status and tracking before replying."
    return {
        "procedure_name": "order_delivery_procedure",
        "procedure_notes": [
            "Use placeholders for date, carrier, and tracking link when shipment details are unavailable.",
            ticket_context["note"],
        ],
        "draft_subject": subject,
        "draft_response_seed": response,
        "ai_summary_seed": summary,
        "validation_questions": [
            "Confirm the order number before sending.",
            "Check whether there is a live shipment scan or pending carrier handoff.",
        ],
        "suggestions": _base_suggestions(
            subject,
            response,
            summary,
            "Confirm carrier, shipping date, and tracking link before final send.",
            "Verify shipment status and any open ticket before replying.",
        ),
    }


def _returns_refunds_tool(
    message: str,
    customer: dict[str, Any],
    payload: dict[str, Any],
    ticket_context: dict[str, Any],
) -> dict[str, Any]:
    first = _first_name(customer.get("name") or payload.get("sender_name") or "Customer")
    subject = "Update on your return and refund"
    response = (
        f"Hi {first},\n\n"
        "Thanks for contacting us about your return. We are reviewing the return status and refund timeline now. "
        "If the return has already been received, the refund will follow the standard processing window. "
        f"{ticket_context['note']}\n\n"
        "If you can share the return number or order number, I can confirm the next step.\n\n"
        "Best regards,\nArcella Customer Care"
    )
    summary = "Customer is asking about a return or refund; confirm return status, timeline, and any matching open ticket."
    return {
        "procedure_name": "returns_refunds_procedure",
        "procedure_notes": [
            "Check return receipt status before quoting any refund timing.",
            ticket_context["note"],
        ],
        "draft_subject": subject,
        "draft_response_seed": response,
        "ai_summary_seed": summary,
        "validation_questions": [
            "Confirm whether the item has been returned or scanned in.",
            "Confirm the refund method before promising timing.",
        ],
        "suggestions": _base_suggestions(
            subject,
            response,
            summary,
            "Verify return receipt and refund processing before final response.",
            "Check return scan status and any related open ticket before replying.",
        ),
    }


def _billing_payment_tool(
    message: str,
    customer: dict[str, Any],
    payload: dict[str, Any],
    ticket_context: dict[str, Any],
) -> dict[str, Any]:
    first = _first_name(customer.get("name") or payload.get("sender_name") or "Customer")
    subject = "Update on your billing and payment enquiry"
    response = (
        f"Hi {first},\n\n"
        "Thanks for reaching out about your billing concern. We are reviewing the payment details, charges, and any refund history now. "
        "If this is a duplicate charge, we will verify the transactions and confirm the next steps. "
        f"{ticket_context['note']}\n\n"
        "If you can share the invoice or last four digits of the card used, I can narrow this down further.\n\n"
        "Best regards,\nArcella Customer Care"
    )
    summary = "Customer has a billing or payment issue; verify charge history, refund status, or payment failure."
    return {
        "procedure_name": "billing_payment_procedure",
        "procedure_notes": [
            "Review payment history and any duplicate charge indicators before replying.",
            ticket_context["note"],
        ],
        "draft_subject": subject,
        "draft_response_seed": response,
        "ai_summary_seed": summary,
        "validation_questions": [
            "Confirm whether this is a duplicate charge, refund delay, or payment failure.",
            "Confirm whether the customer can share an invoice or last four digits for verification.",
        ],
        "suggestions": _base_suggestions(
            subject,
            response,
            summary,
            "Check transaction history and refund status before final send.",
            "Verify payment details and customer identity before replying.",
        ),
    }


def _account_management_tool(
    message: str,
    customer: dict[str, Any],
    payload: dict[str, Any],
    ticket_context: dict[str, Any],
) -> dict[str, Any]:
    first = _first_name(customer.get("name") or payload.get("sender_name") or "Customer")
    subject = "Help with your account"
    response = (
        f"Hi {first},\n\n"
        "Thanks for reaching out. We can help with your account access and updates. "
        "If this is a password or login issue, the next step is to verify your account details and send the appropriate reset or recovery steps. "
        f"{ticket_context['note']}\n\n"
        "Please reply with the best contact method and any relevant account detail so we can continue.\n\n"
        "Best regards,\nArcella Customer Care"
    )
    summary = "Customer needs account assistance such as login recovery or profile updates."
    return {
        "procedure_name": "account_management_procedure",
        "procedure_notes": [
            "Verify identity before any account change or reset.",
            ticket_context["note"],
        ],
        "draft_subject": subject,
        "draft_response_seed": response,
        "ai_summary_seed": summary,
        "validation_questions": [
            "Confirm the exact account action requested.",
            "Confirm the preferred contact method for verification steps.",
        ],
        "suggestions": _base_suggestions(
            subject,
            response,
            summary,
            "Follow identity verification before performing any account updates.",
            "Verify account ownership and route to the correct account procedure.",
        ),
    }


def _general_enquiry_tool(
    message: str,
    customer: dict[str, Any],
    payload: dict[str, Any],
    ticket_context: dict[str, Any],
) -> dict[str, Any]:
    first = _first_name(customer.get("name") or payload.get("sender_name") or "Customer")
    subject = "Thanks for contacting Arcella"
    response = (
        f"Hi {first},\n\n"
        "Thanks for reaching out. We have reviewed your enquiry and are working through the details. "
        "If you can share any additional context, screenshots, or reference numbers, that will help us confirm the best next step. "
        f"{ticket_context['note']}\n\n"
        "Best regards,\nArcella Customer Care"
    )
    summary = "General customer enquiry that needs a helpful response and possibly more context."
    return {
        "procedure_name": "general_enquiry_procedure",
        "procedure_notes": [
            "Ask for any missing reference data needed to complete the response.",
            ticket_context["note"],
        ],
        "draft_subject": subject,
        "draft_response_seed": response,
        "ai_summary_seed": summary,
        "validation_questions": [
            "Confirm whether more context or reference numbers are needed.",
            "Confirm whether the enquiry should be routed to another team.",
        ],
        "suggestions": _base_suggestions(
            subject,
            response,
            summary,
            "Capture any extra context needed before closing the enquiry.",
            "Request missing details and route if the issue belongs to another team.",
        ),
    }


def _draft_enquiry_email(
    message: str,
    customer: dict[str, Any],
    classification: dict[str, Any],
    procedure: dict[str, Any],
    ticket_context: dict[str, Any],
) -> dict[str, Any]:
    first = _first_name(customer.get("name") or "Customer")
    brief = f"""## Enquiry Draft Brief

Customer name: {customer.get('name', 'Customer')}
Customer email: {customer.get('email', '')}
Customer tier: {customer.get('tier', 'Bronze')}
Customer first name: {first}

Classification:
- Category: {classification['category']}
- Subcategory: {classification['subcategory']}
- Confidence: {classification['confidence']:.2f}
- Sentiment: {classification['sentiment_label']} ({classification['sentiment_score']:.2f})
- Urgency score: {classification['urgency_score']}
- Priority: {classification['priority']}

Procedure notes:
{chr(10).join(f"- {n}" for n in procedure['procedure_notes'])}

Ticket context:
{ticket_context['note']}

Source message:
{message}

Required style:
- Write a concise, helpful customer email.
- Use placeholders like [date], [carrier/mode], and [tracking link] when hard data is unavailable.
- If the message is about order/delivery, mention whether we see an open ticket or no ticket filed.
- Keep it professional, warm, and under 180 words.
- Return only JSON with keys: draft_subject, draft_response, ai_summary.
"""

    try:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        response = litellm.completion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": ENQUIRY_SYSTEM_PROMPT},
                {"role": "user", "content": brief},
            ],
            temperature=0.25,
            max_tokens=700,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_enquiry_response(raw, procedure)
    except Exception as exc:
        logger.warning("Enquiry drafting LLM failed, using template fallback: %s", exc)
        return {
            "draft_subject": procedure["draft_subject"],
            "draft_response": procedure["draft_response_seed"],
            "ai_summary": procedure["ai_summary_seed"],
        }


ENQUIRY_SYSTEM_PROMPT = """You are an enquiry response writer for an e-commerce support team.

You must return ONLY valid JSON with these keys:
{
  "draft_subject": "<short subject line>",
  "draft_response": "<customer-facing email>",
  "ai_summary": "<short internal summary>"
}

Rules:
- Be concise and helpful.
- If exact order or shipment details are unavailable, use placeholders like [date], [carrier/mode], and [tracking link].
- If the message is about order or delivery, mention whether there is an open ticket or no ticket filed.
- Reference the customer by first name.
- Do not add markdown fences or commentary.
"""


def _parse_enquiry_response(raw: str, procedure: dict[str, Any]) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    data = json.loads(cleaned)
    required = {"draft_subject", "draft_response", "ai_summary"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Enquiry response missing keys: {missing}")
    return {
        "draft_subject": str(data.get("draft_subject") or procedure["draft_subject"]).strip(),
        "draft_response": str(data.get("draft_response") or procedure["draft_response_seed"]).strip(),
        "ai_summary": str(data.get("ai_summary") or procedure["ai_summary_seed"]).strip(),
    }


def _apply_draft_to_suggestions(suggestions: list[dict[str, Any]], draft: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for item in suggestions:
        cloned = dict(item)
        if cloned["id"] == "subject":
            cloned["text"] = draft["draft_subject"]
        elif cloned["id"] == "response":
            cloned["text"] = draft["draft_response"]
        elif cloned["id"] == "summary":
            cloned["text"] = draft["ai_summary"]
        output.append(cloned)
    return output


def _first_name(value: str) -> str:
    value = (value or "Customer").strip()
    if not value:
        return "Customer"
    return value.split()[0]
