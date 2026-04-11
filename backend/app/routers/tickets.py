# app/routers/tickets.py
"""
GET    /api/tickets          -- list all tickets (with Snowflake JOIN + triage mapping)
PATCH  /api/tickets          -- update ticket status / resolution
POST   /api/tickets/create   -- create a new ticket in STORE_RETURNS
"""
from __future__ import annotations
import logging
import math
import random
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.db import run_query
from app.models import (
    TicketListResponse, TicketResponse, TicketItemModel,
    TicketCustomerModel, TicketTriageModel,
    UpdateTicketRequest, UpdateTicketResponse,
    CreateTicketRequest, CreateTicketResponse,
)

logger = logging.getLogger("routers.tickets")

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/tickets
# ═══════════════════════════════════════════════════════════════════════════

@router.get("", response_model=TicketListResponse, summary="List all support tickets")
async def list_tickets(
    limit:  int = Query(50, ge=1, le=500),
    offset: int = Query(0,  ge=0),
) -> TicketListResponse:
    try:
        rows = run_query(
            f"""
            SELECT
                sr.SR_TICKET_NUMBER,
                sr.SR_RETURN_AMT,
                sr.SR_FEE,
                sr.SR_NET_LOSS,
                sr.SR_RETURN_QUANTITY,
                r.R_REASON_SK,
                r.R_REASON_ID,
                r.R_REASON_DESC,
                i.I_ITEM_SK,
                i.I_PRODUCT_NAME,
                i.I_CATEGORY,
                i.I_CATEGORY_FULL,
                i.I_CLASS,
                i.I_BRAND,
                i.I_CURRENT_PRICE,
                i.I_LIST_PRICE,
                i.I_ITEM_DESC,
                i.I_PRODUCT_URL,
                c.C_CUSTOMER_SK,
                c.C_FIRST_NAME,
                c.C_LAST_NAME,
                c.C_EMAIL_ADDRESS,
                c.C_PREFERRED_CUST_FLAG,
                d.D_DATE,
                COALESCE(sr.SR_STATUS, 'Open')   AS SR_STATUS,
                COALESCE(sr.SR_RESOLUTION, '')   AS SR_RESOLUTION,
                COALESCE(rc.RETURN_COUNT, 0)     AS CUSTOMER_ORDER_COUNT
            FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS sr
                LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.REASON r
                    ON r.R_REASON_SK = sr.SR_REASON_SK
                LEFT JOIN (
                    SELECT *,
                           ROW_NUMBER() OVER (ORDER BY I_ITEM_SK) AS I_RN
                    FROM SYNTHETIC_COMPANYDB.COMPANY.ITEM
                    WHERE I_AVAILABLE = TRUE
                ) i ON i.I_RN = sr.SR_ITEM_SK
                LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
                    ON c.C_CUSTOMER_SK = sr.SR_CUSTOMER_SK
                LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.DATE_DIM d
                    ON d.D_DATE_SK = sr.SR_RETURNED_DATE_SK
                LEFT JOIN (
                    SELECT SR_CUSTOMER_SK,
                           COUNT(DISTINCT SR_TICKET_NUMBER) AS RETURN_COUNT
                    FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS
                    WHERE SR_CUSTOMER_SK IS NOT NULL
                    GROUP BY SR_CUSTOMER_SK
                ) rc ON rc.SR_CUSTOMER_SK = sr.SR_CUSTOMER_SK
            ORDER BY sr.SR_RETURNED_DATE_SK DESC, sr.SR_TICKET_NUMBER
            LIMIT {limit} OFFSET {offset}
            """
        )

        # Deduplicate by ticket number, keeping highest net_loss row
        seen: dict[str, Any] = {}
        for row in rows:
            key = str(row.get("SR_TICKET_NUMBER") or id(row))
            existing = seen.get(key)
            net_loss = float(row.get("SR_NET_LOSS") or 0)
            if not existing or net_loss > float(existing.get("SR_NET_LOSS") or 0):
                seen[key] = row

        tickets = [_map_row_to_ticket(r, i) for i, r in enumerate(seen.values())]
        return TicketListResponse(tickets=tickets, total=len(tickets))

    except Exception as exc:
        logger.error("[GET /api/tickets] ERROR: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to fetch tickets: {exc}") from exc


# ═══════════════════════════════════════════════════════════════════════════
# PATCH /api/tickets
# ═══════════════════════════════════════════════════════════════════════════

@router.patch("", response_model=UpdateTicketResponse, summary="Update ticket status")
async def update_ticket(body: UpdateTicketRequest) -> UpdateTicketResponse:
    ticket_number = body.id.replace("TKT-", "")

    set_clauses = [f"SR_STATUS = '{body.status}'"]
    if body.resolution:
        safe_res = body.resolution.replace("'", "''")
        set_clauses.append(f"SR_RESOLUTION = '{safe_res}'")

    sql = (
        f"UPDATE SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS "
        f"SET {', '.join(set_clauses)} "
        f"WHERE SR_TICKET_NUMBER = '{ticket_number}'"
    )
    logger.info("[PATCH /api/tickets] %s", sql)

    try:
        run_query(sql)
    except Exception as exc:
        logger.error("[PATCH /api/tickets] ERROR: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to update ticket: {exc}") from exc

    return UpdateTicketResponse(
        ok=True,
        id=body.id,
        status=body.status,
        resolution=body.resolution,
    )


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/tickets/create
# ═══════════════════════════════════════════════════════════════════════════

@router.post(
    "/create",
    response_model=CreateTicketResponse,
    summary="Create a new support ticket in Snowflake",
)
async def create_ticket(body: CreateTicketRequest) -> CreateTicketResponse:
    # Validate required fields
    if not body.customer.name or not body.customer.email:
        raise HTTPException(status_code=400, detail="Customer name and email are required")

    if body.ticket_type == "return":
        if not body.item or not body.item.name or not body.item.category:
            raise HTTPException(status_code=400, detail="Item name and category are required for returns")
        if not body.reason_desc:
            raise HTTPException(status_code=400, detail="Return reason description is required")

    if body.ticket_type == "enquiry":
        if not body.enquiry_subject:
            raise HTTPException(status_code=400, detail="Enquiry subject is required")

    # Generate unique ticket number in 99100xxxxx range
    ts_part = str(int(time.time()))[-8:]
    rand_part = str(random.randint(0, 99)).zfill(2)
    ticket_number = f"9910{ts_part}{rand_part}"[:12]

    try:
        # Resolve customer SK
        customer_sk = body.customer.sk
        if not customer_sk:
            try:
                rows = run_query(
                    """
                    SELECT C_CUSTOMER_SK FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER
                    WHERE LOWER(C_EMAIL_ADDRESS) = LOWER(%s)
                    LIMIT 1
                    """,
                    (body.customer.email,),
                )
                if rows:
                    customer_sk = rows[0]["C_CUSTOMER_SK"]
            except Exception as e:
                logger.warning("[create] Customer lookup failed (non-fatal): %s", e)

        if not customer_sk:
            try:
                rows = run_query(
                    "SELECT C_CUSTOMER_SK FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER LIMIT 1"
                )
                if rows:
                    customer_sk = rows[0]["C_CUSTOMER_SK"]
            except Exception:
                customer_sk = 1

        # Resolve item SK (rank) to store in SR_ITEM_SK
        # Priority: use rn sent by frontend (already correct rank) →
        #           fallback: look up rank by sk → last resort: 1
        item_sk = 1
        if body.item and body.item.rn:
            item_sk = body.item.rn
            logger.info("[create] Using item rank from request: I_RN=%s (I_ITEM_SK=%s)", item_sk, body.item.sk)
        elif body.item and body.item.sk:
            try:
                rows = run_query(
                    """
                    SELECT I_RN FROM (
                        SELECT I_ITEM_SK,
                               ROW_NUMBER() OVER (ORDER BY I_ITEM_SK) AS I_RN
                        FROM SYNTHETIC_COMPANYDB.COMPANY.ITEM
                        WHERE I_AVAILABLE = TRUE
                    ) ranked
                    WHERE I_ITEM_SK = %s
                    LIMIT 1
                    """,
                    (body.item.sk,),
                )
                if rows:
                    item_sk = rows[0]["I_RN"]
                    logger.info("[create] Resolved I_RN=%s for I_ITEM_SK=%s", item_sk, body.item.sk)
            except Exception as e:
                logger.warning("[create] Item rank lookup failed, defaulting to 1: %s", e)
        else:
            logger.warning("[create] No item SK/RN in request, defaulting SR_ITEM_SK to 1")

        # DATE_DIM only covers up to 2003-12-31 in this dataset.
        # Use max available SK so the ticket always has a date row.
        date_sk_clause = "2453005"

        # Financials
        return_amt = float(body.return_amt or 0)
        net_loss   = float(body.net_loss   or 0)
        fee        = round(return_amt * 0.10, 2)
        return_qty = int(body.item.return_qty if body.item else 1)

        # reason_sk: use provided value or default to 1 (free text reason stored in SR_RESOLUTION)
        reason_sk = int(body.reason_sk or 1)

        # Build a rich structured resolution string combining all context:
        # product details + packaging assessment + financials + agent reason + complaint
        item_name     = body.item.name     if body.item else 'Unknown Item'
        item_brand    = body.item.brand    if body.item else ''
        item_category = body.item.category if body.item else ''
        item_price    = body.item.price    if body.item else '0'
        qty           = return_qty

        pkg_label_map = {
            'sealed':    'Sealed / Unopened (0% degradation)',
            'intact':    'Intact / Good (+10% degradation)',
            'minor':     'Minor Damage (+25% degradation)',
            'moderate':  'Moderate Damage (+50% degradation)',
            'heavy':     'Heavily Damaged (+80% degradation)',
            'destroyed': 'Destroyed / Unusable (+100% degradation)',
        }
        pkg_condition = body.packaging_condition or ''
        pkg_label     = pkg_label_map.get(pkg_condition, pkg_condition or 'Not assessed')
        pkg_factor    = float(body.packaging_factor or 0)

        brand_str    = f' ({item_brand})' if item_brand else ''
        category_str = f' [{item_category}]' if item_category else ''

        resolution_parts = [
            f'ITEM: {item_name}{brand_str}{category_str}',
            f'UNIT PRICE: ${float(item_price):.2f} | QTY RETURNED: {qty} | TOTAL VALUE: ${float(item_price) * qty:.2f}',
            f'PACKAGING ASSESSMENT: {pkg_label}',
            f'FINANCIALS: Return Amt ${return_amt:.2f} | Fee ${fee:.2f} | Net Loss ${net_loss:.2f} (formula: ${return_amt:.2f} x 0.4 x {1 + pkg_factor:.2f})',
        ]

        if body.reason_desc:
            resolution_parts.append(f'RETURN REASON: {body.reason_desc}')

        if body.complaint_desc:
            resolution_parts.append(f'AGENT NOTES: {body.complaint_desc}')

        resolution_text = ' | '.join(resolution_parts)
        safe_resolution = resolution_text.replace("'", "''")

        insert_sql = f"""
            INSERT INTO SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS (
                SR_TICKET_NUMBER,
                SR_ITEM_SK,
                SR_CUSTOMER_SK,
                SR_REASON_SK,
                SR_RETURNED_DATE_SK,
                SR_RETURN_AMT,
                SR_FEE,
                SR_NET_LOSS,
                SR_RETURN_QUANTITY,
                SR_STATUS,
                SR_RESOLUTION
            ) VALUES (
                '{ticket_number}',
                {item_sk},
                {customer_sk},
                {reason_sk},
                {date_sk_clause},
                {return_amt},
                {fee},
                {net_loss},
                {return_qty},
                'Open',
                '{safe_resolution}'
            )
        """
        logger.info("[POST /api/tickets/create] SQL: %s", insert_sql)
        run_query(insert_sql)

        ticket_id = f"TKT-{ticket_number}"
        logger.info("[POST /api/tickets/create] Created: %s", ticket_id)

        return CreateTicketResponse(
            ok=True,
            ticketId=ticket_id,
            ticketNumber=ticket_number,
            message=f"Ticket {ticket_id} created successfully",
        )

    except Exception as exc:
        msg = str(exc)
        logger.error("[POST /api/tickets/create] ERROR: %s", msg)

        # Graceful demo fallback if Snowflake INSERT is rejected
        if any(kw in msg for kw in ["insufficient privileges", "not authorized", "READ_ONLY"]):
            mock_id = f"TKT-DEMO-{str(int(time.time()))[-6:]}"
            logger.warning("[create] Snowflake INSERT not permitted — returning mock: %s", mock_id)
            return CreateTicketResponse(
                ok=True,
                ticketId=mock_id,
                ticketNumber=mock_id.replace("TKT-", ""),
                message=f"Demo ticket {mock_id} created (Snowflake INSERT not available)",
                demo=True,
            )

        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {msg}") from exc


# ═══════════════════════════════════════════════════════════════════════════
# Mapping helpers  (ported from src/routes/api/tickets/+server.js)
# ═══════════════════════════════════════════════════════════════════════════

def _map_row_to_ticket(row: dict, idx: int) -> TicketResponse:
    ticket_num  = row.get("SR_TICKET_NUMBER")
    return_amt  = float(row.get("SR_RETURN_AMT")      or 0)
    net_loss    = float(row.get("SR_NET_LOSS")         or 0)
    return_qty  = int(row.get("SR_RETURN_QUANTITY")    or 1)

    first_name  = row.get("C_FIRST_NAME")   or ""
    last_name   = row.get("C_LAST_NAME")    or ""
    email       = row.get("C_EMAIL_ADDRESS") or f"customer-{ticket_num}@unknown.com"
    preferred   = row.get("C_PREFERRED_CUST_FLAG") == "Y"

    reason_desc = row.get("R_REASON_DESC") or f"Reason #{row.get('SR_REASON_SK', 'unknown')}"
    return_date = row.get("D_DATE")

    product_name    = row.get("I_PRODUCT_NAME")   or f"Item #{row.get('SR_ITEM_SK', 'unknown')}"
    category        = row.get("I_CATEGORY")       or "General"
    category_full   = row.get("I_CATEGORY_FULL")  or category
    item_class      = row.get("I_CLASS")          or ""
    item_brand      = row.get("I_BRAND")          or ""
    item_price      = float(row.get("I_CURRENT_PRICE") or 0)
    item_list_price = float(row.get("I_LIST_PRICE")    or item_price)
    item_desc       = (row.get("I_ITEM_DESC") or "")[:300]
    item_url        = row.get("I_PRODUCT_URL") or ""

    ticket_id = f"TKT-{ticket_num or idx + 1}"

    sentiment_score = (
        -0.85 if net_loss > 500 else
        -0.65 if net_loss > 200 else
        -0.40 if net_loss > 50  else -0.15
    )
    sentiment = (
        "frustrated"   if sentiment_score <= -0.7 else
        "dissatisfied" if sentiment_score <= -0.4 else "neutral"
    )

    issue_type = _reason_to_issue_type(reason_desc)
    escalation = ["high_value_return"] if (net_loss > 500 or return_qty > 5) else []
    triage_data = _build_triage(reason_desc, category, item_price, return_amt, return_qty, net_loss, preferred)

    tier = (
        "Gold"   if preferred and return_amt > 300 else
        "Silver" if preferred else "Bronze"
    )

    override = triage_data.get("priorityOverride")
    final_priority = override if override else (
        "critical" if net_loss > 500 else
        "high"     if net_loss > 200 else
        "medium"   if net_loss > 50  else "low"
    )

    created_str = (
        return_date.isoformat() if hasattr(return_date, "isoformat")
        else (str(return_date) if return_date else datetime.now(timezone.utc).isoformat())
    )

    issues = [
        {"type": issue_type, "subtype": "return_request", "entity": f"Order #{ticket_num}", "confidence": 0.95},
        *([{"type": "complaint_billing", "subtype": "refund_request", "entity": f"${return_amt:.2f}", "confidence": 0.88}] if net_loss > 200 else []),
        *([{"type": "return_request", "confidence": 0.99}] if return_qty > 3 else []),
        *([{"type": "churn_signal", "confidence": 0.72}] if escalation else []),
    ]

    return TicketResponse(
        id=ticket_id,
        returnAmt=f"{return_amt:.2f}",
        netLoss=f"{net_loss:.2f}",
        fee=f"{float(row.get('SR_FEE') or 0):.2f}",
        returnReason=reason_desc,
        customer=TicketCustomerModel(
            name=f"{first_name} {last_name}".strip() or "Unknown Customer",
            email=email,
            tier=tier,
            ltv=str(int(return_amt * 3.5)),
            orders=int(row.get("CUSTOMER_ORDER_COUNT") or 0),
        ),
        item=TicketItemModel(
            name=product_name,
            category=category,
            category_full=category_full,
            **{"class": item_class},
            brand=item_brand,
            price=f"{item_price:.2f}",
            listPrice=f"{item_list_price:.2f}",
            desc=item_desc,
            url=item_url,
            returnQty=return_qty,
        ),
        subject=f"Return -- {product_name} ({reason_desc})",
        preview=(
            f"{first_name} is returning {return_qty}x {product_name} ({category}). "
            f"Reason: {reason_desc}. Return amount: ${return_amt:.2f}."
        ),
        channel="email",
        created=created_str,
        updated=created_str,
        status=(row.get("SR_STATUS") or "Open"),
        resolution=(row.get("SR_RESOLUTION") or None),
        priority=final_priority,
        triage=TicketTriageModel(
            action=triage_data.get("action", ""),
            actionLabel=triage_data.get("actionLabel", ""),
            actionRationale=triage_data.get("actionRationale", ""),
            refundSignal=triage_data.get("refundSignal", {}),
            policyRef=triage_data.get("policyRef", ""),
            flags=triage_data.get("flags", []),
            priorityOverride=triage_data.get("priorityOverride"),
        ),
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        urgency=5 if final_priority == "critical" else 4 if final_priority == "high" else 2 if final_priority == "medium" else 1,
        department="billing" if "billing" in issue_type else "fulfillment",
        issues=issues,
        escalation_signals=escalation,
        ai_draft=None,
        ai_citations=[],
        supervisor={
            "approved": False,
            "recommendation": "revise",
            "confidence_score": 0.6,
            "failures": [{"type": "DRAFT_PENDING", "severity": "medium", "detail": "AI draft not yet generated"}],
        },
    )


def _reason_to_issue_type(desc: str) -> str:
    d = desc.lower()
    if "damaged" in d or "broken" in d:          return "complaint_product"
    if "time" in d or "late" in d:               return "complaint_shipping"
    if "not the right" in d or "wrong" in d:     return "complaint_product"
    if "no longer needed" in d:                   return "return_request"
    if "work" in d or "defect" in d:             return "complaint_product"
    if "price" in d or "charge" in d:            return "complaint_billing"
    return "general_inquiry"


def _build_triage(
    reason_desc: str, category: str, item_price: float,
    return_amt: float, return_qty: int, net_loss: float, preferred: bool,
) -> dict:
    r = reason_desc.lower()
    c = category.lower()

    is_damaged    = "damaged"  in r or "broken" in r
    is_wrong_item = "not the right" in r or "wrong" in r
    is_defective  = "work" in r or "defect" in r or "stopped" in r
    is_unwanted   = "no longer needed" in r or "unwanted" in r
    is_size_fit   = "size" in r or "fit" in r or "too small" in r or "too large" in r
    is_late_slow  = "time" in r or "late" in r or "slow" in r

    is_electronics = any(k in c for k in ["electronics", "computers", "music", "jewelry"])
    is_apparel     = any(k in c for k in ["clothing", "apparel", "women", "men", "children", "shoes", "sports"])
    is_high_value  = item_price > 200 or return_amt > 200
    is_bulk        = return_qty > 1

    priority_override = None
    if is_damaged and is_electronics:        priority_override = "critical"
    elif is_defective and is_electronics:    priority_override = "critical"
    elif is_bulk and return_qty > 5:         priority_override = "high"
    elif is_unwanted and is_high_value and preferred: priority_override = "high"

    if is_damaged and is_electronics:
        action = "replacement_escalate"
        action_label = "Replace & Escalate to Quality Team"
        rationale = "Damaged electronics require replacement and a quality team review to flag potential batch defects."
    elif is_damaged:
        action = "replacement"
        action_label = "Send Replacement"
        rationale = "Item arrived damaged -- direct replacement is the fastest resolution."
    elif is_defective:
        action = "replacement"
        action_label = "Send Replacement"
        rationale = f"Product stopped working. {'Escalate to quality team after replacing.' if is_electronics else 'Issue replacement immediately.'}"
    elif is_wrong_item or is_size_fit:
        if is_apparel:
            action = "exchange_first"
            action_label = "Offer Size Exchange First"
            rationale = "Wrong size or fit on apparel -- offer an exchange before initiating a refund to preserve the sale."
        else:
            action = "replacement"
            action_label = "Send Correct Item"
            rationale = "Wrong item was shipped -- send the correct one and arrange return of original."
    elif is_unwanted:
        if is_high_value and preferred:
            action = "retention_offer"
            action_label = "Retention Offer Before Refund"
            rationale = f"High-value item (${item_price:.0f}) from a preferred customer. Offer a discount or store credit before processing the refund to reduce churn risk."
        else:
            action = "refund"
            action_label = "Process Refund"
            rationale = "Customer no longer needs the item -- standard refund."
    elif is_late_slow:
        action = "refund_or_reship"
        action_label = "Refund or Reship"
        rationale = "Late delivery -- offer customer choice of full refund or expedited reship."
    else:
        action = "refund"
        action_label = "Process Refund"
        rationale = "Standard return -- process refund per policy."

    if return_amt < item_price * 0.9:
        refund_signal = {"type": "partial", "note": f"Return amount (${return_amt:.2f}) is less than item price (${item_price:.2f}) -- likely a partial return."}
    elif is_bulk:
        refund_signal = {"type": "bulk", "note": f"{return_qty} units returned -- bulk return, verify all units before issuing full refund."}
    else:
        refund_signal = {"type": "full", "note": "Full single-unit return -- standard full refund."}

    policy_ref = (
        "Electronics Return Policy section 4.2 -- 15-day return window, must be unopened or defective"
        if is_electronics else
        "Apparel Return Policy section 3.1 -- 30-day return window, tags must be attached"
        if is_apparel else
        "General Return Policy section 2.1 -- 30-day return window"
    )

    flags = []
    if is_damaged and is_electronics:
        flags.append({"type": "quality_escalation", "label": "Quality Team Alert", "severity": "high"})
    if is_bulk and return_qty > 3:
        flags.append({"type": "bulk_return", "label": f"Bulk Return ({return_qty} units)", "severity": "medium"})
    if is_unwanted and is_high_value and preferred:
        flags.append({"type": "churn_risk", "label": "Churn Risk -- Preferred Customer", "severity": "high"})
    if net_loss > 500:
        flags.append({"type": "high_loss", "label": f"High Net Loss (${net_loss:.2f})", "severity": "critical"})

    return {
        "action":          action,
        "actionLabel":     action_label,
        "actionRationale": rationale,
        "refundSignal":    refund_signal,
        "policyRef":       policy_ref,
        "flags":           flags,
        "priorityOverride": priority_override,
    }
