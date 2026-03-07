# app/routers/suggest_reason.py
"""
POST /api/suggest-reason

Accepts the complaint description, packaging condition, item name and category,
and returns a plain-text suggested return reason using LiteLLM → gpt-4o-mini.

Falls back to keyword-based logic if the LLM call fails, so the endpoint
always returns a 200 — the frontend never needs to handle a failure here.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger("routers.suggest_reason")
settings = get_settings()

router = APIRouter(prefix="/api/suggest-reason", tags=["suggest-reason"])


# ── Request / Response ────────────────────────────────────────────────────

class SuggestReasonRequest(BaseModel):
    complaint_desc: str = ""
    packaging_condition: str = ""   # sealed | intact | minor | moderate | heavy | destroyed
    item_name: str = ""
    item_category: str = ""


class SuggestReasonResponse(BaseModel):
    reason_desc: str
    source: str   # "llm" | "fallback"


# ── Endpoint ──────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=SuggestReasonResponse,
    summary="AI-suggest a return reason from complaint + packaging assessment",
)
async def suggest_reason(req: SuggestReasonRequest) -> SuggestReasonResponse:

    # Try LLM first
    try:
        reason_text = await _llm_suggest(req)
        return SuggestReasonResponse(reason_desc=reason_text, source="llm")
    except Exception as exc:
        logger.warning("[suggest_reason] LLM failed, using fallback: %s", exc)

    # Always succeed with keyword fallback
    return SuggestReasonResponse(
        reason_desc=_keyword_suggest(req.complaint_desc, req.packaging_condition),
        source="fallback",
    )


# ── LLM helper ────────────────────────────────────────────────────────────

async def _llm_suggest(req: SuggestReasonRequest) -> str:
    from litellm import acompletion

    packaging_labels = {
        "sealed":    "Sealed / Unopened — original seal intact",
        "intact":    "Intact / Good — opened but undamaged",
        "minor":     "Minor Damage — small dents or scuffs",
        "moderate":  "Moderate Damage — visible, partially compromised",
        "heavy":     "Heavily Damaged — significantly damaged",
        "destroyed": "Destroyed / Unusable — packaging completely destroyed",
    }
    pkg_label = packaging_labels.get(req.packaging_condition, req.packaging_condition or "unknown")

    prompt = f"""You are a customer support agent writing a concise return reason for an internal ticket.

Item: {req.item_name or 'Unknown'} ({req.item_category or 'Unknown category'})
Packaging condition assessed: {pkg_label}
Customer complaint: {req.complaint_desc or 'No description provided'}

Write a single clear sentence (max 20 words) summarising the return reason for this ticket.
Return ONLY the sentence, no preamble, no punctuation at the end."""

    response = await acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY,
    )
    return response.choices[0].message.content.strip()


# ── Keyword fallback ──────────────────────────────────────────────────────

def _keyword_suggest(complaint: str, packaging: str) -> str:
    d = complaint.lower()
    p = packaging

    if p in ("destroyed", "heavy"):
        return "Package was heavily damaged on arrival — item exposed and potentially unusable"
    if p == "moderate":
        return "Packaging shows significant damage, compromising product integrity"
    if p == "minor":
        return "Minor packaging damage observed; product may have minor cosmetic issues"
    if "not working" in d or "stopped" in d or "broken" in d:
        return "Product stopped working after a short period of use"
    if "late" in d or "delay" in d or "not arrive" in d:
        return "Item did not arrive on time — delivery was significantly delayed"
    if "wrong" in d or "not what" in d or "incorrect" in d:
        return "Received the wrong product — does not match what was ordered"
    if "missing" in d or "parts" in d or "incomplete" in d:
        return "Parts or accessories were missing from the package"
    if "defect" in d or "damaged" in d or "crack" in d:
        return "Product arrived in a defective or damaged condition"
    if "size" in d or "fit" in d or "too small" in d or "too large" in d:
        return "Item does not fit — wrong size for the customer"
    return "Customer is unsatisfied with the product and is requesting a return"
