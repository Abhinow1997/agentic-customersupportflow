# app/routers/suggest_reason.py
"""
POST /api/suggest-reason

Accepts full product details + packaging assessment + complaint description
and returns an AI-generated return reason sentence using gpt-4o-mini.

Falls back to keyword logic if the LLM call fails — always returns 200.
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
    # complaint
    complaint_desc: str = ""
    # packaging assessment
    packaging_condition: str = ""   # sealed | intact | minor | moderate | heavy | destroyed
    packaging_factor: float = 0.0   # numeric degradation factor e.g. 0.50
    # full item details from /api/items lookup
    item_name: str = ""
    item_brand: str = ""
    item_category: str = ""
    item_category_full: str = ""
    item_class: str = ""
    item_price: str = ""
    item_list_price: str = ""
    item_desc: str = ""             # product description (may be long — trimmed before sending)
    item_package_size: str = ""
    # return financials
    return_qty: int = 1
    return_amt: str = ""
    net_loss: str = ""


class SuggestReasonResponse(BaseModel):
    reason_desc: str
    source: str   # "llm" | "fallback"


# ── Endpoint ──────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=SuggestReasonResponse,
    summary="AI-suggest a return reason using full product context",
)
async def suggest_reason(req: SuggestReasonRequest) -> SuggestReasonResponse:
    try:
        reason_text = await _llm_suggest(req)
        return SuggestReasonResponse(reason_desc=reason_text, source="llm")
    except Exception as exc:
        logger.warning("[suggest_reason] LLM failed, using fallback: %s", exc)

    return SuggestReasonResponse(
        reason_desc=_keyword_suggest(req.complaint_desc, req.packaging_condition),
        source="fallback",
    )


# ── LLM helper ────────────────────────────────────────────────────────────

async def _llm_suggest(req: SuggestReasonRequest) -> str:
    from litellm import acompletion

    # Packaging condition human labels + degradation %
    packaging_labels = {
        "sealed":    "Sealed / Unopened — original seal intact (0% degradation)",
        "intact":    "Intact / Good — opened but packaging undamaged (+10% degradation)",
        "minor":     "Minor Damage — small dents or scuffs (+25% degradation)",
        "moderate":  "Moderate Damage — visible damage, partially compromised (+50% degradation)",
        "heavy":     "Heavily Damaged — significantly damaged, hard to resell (+80% degradation)",
        "destroyed": "Destroyed / Unusable — packaging completely destroyed (+100% degradation)",
    }
    pkg_label = packaging_labels.get(
        req.packaging_condition,
        req.packaging_condition or "Not assessed"
    )

    # Build product context block — trim long desc to avoid token waste
    item_desc_trimmed = (req.item_desc or "")[:300]
    category_full = req.item_category_full or req.item_category

    product_lines = []
    if req.item_name:        product_lines.append(f"  Product Name   : {req.item_name}")
    if req.item_brand:       product_lines.append(f"  Brand          : {req.item_brand}")
    if category_full:        product_lines.append(f"  Category       : {category_full}")
    if req.item_class:       product_lines.append(f"  Class          : {req.item_class}")
    if req.item_price:       product_lines.append(f"  Unit Price     : ${req.item_price}")
    if req.item_package_size:product_lines.append(f"  Package Size   : {req.item_package_size}")
    if item_desc_trimmed:    product_lines.append(f"  Description    : {item_desc_trimmed}")

    return_lines = []
    if req.return_qty > 1:   return_lines.append(f"  Qty Returned   : {req.return_qty}")
    if req.return_amt:       return_lines.append(f"  Return Amount  : ${req.return_amt}")
    if req.net_loss:         return_lines.append(f"  Est. Net Loss  : ${req.net_loss}")

    prompt = f"""You are a customer support agent writing a formal return reason for an internal support ticket.

--- PRODUCT DETAILS ---
{chr(10).join(product_lines) if product_lines else '  (no product details provided)'}

--- PACKAGING ASSESSMENT ---
  Condition      : {pkg_label}
  Degradation    : {int(req.packaging_factor * 100)}% applied to net loss calculation

--- RETURN FINANCIALS ---
{chr(10).join(return_lines) if return_lines else '  (no financial details provided)'}

--- CUSTOMER COMPLAINT ---
{req.complaint_desc or '(no complaint description provided)'}

Using the product details, packaging condition and customer complaint above, write a single clear sentence \
(maximum 30 words) that describes the return reason for this ticket. \
Reference the specific product name and packaging condition in the sentence. \
Return ONLY the sentence — no preamble, no bullet points, no trailing punctuation."""

    logger.info("[suggest_reason] Sending prompt to gpt-4o-mini (%d chars)", len(prompt))

    response = await acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY,
    )
    result = response.choices[0].message.content.strip().rstrip(".")
    logger.info("[suggest_reason] LLM result: %s", result)
    return result


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
