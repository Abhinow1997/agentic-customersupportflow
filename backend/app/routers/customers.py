# app/routers/customers.py
"""
GET /api/customers?email=...

Looks up an existing customer by email address from Snowflake CUSTOMER table.
Returns customer details if found, or { found: false } if not.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query

from app.db import run_query
from app.models import CustomerLookupResponse, CustomerLookupResult

logger = logging.getLogger("routers.customers")

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get(
    "",
    response_model=CustomerLookupResponse,
    summary="Look up a customer by email address",
)
async def lookup_customer(
    email: str = Query(..., description="Customer email address to search for"),
) -> CustomerLookupResponse:

    if not email.strip():
        raise HTTPException(status_code=400, detail="email query parameter is required")

    try:
        # Confirmed columns on SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER:
        # C_CUSTOMER_SK, C_FIRST_NAME, C_LAST_NAME, C_EMAIL_ADDRESS, C_PREFERRED_CUST_FLAG
        rows = run_query(
            """
            SELECT
                C_CUSTOMER_SK,
                C_FIRST_NAME,
                C_LAST_NAME,
                C_EMAIL_ADDRESS,
                C_PREFERRED_CUST_FLAG
            FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER
            WHERE LOWER(C_EMAIL_ADDRESS) = LOWER(%s)
            LIMIT 1
            """,
            (email.strip(),),
        )

        if not rows:
            return CustomerLookupResponse(found=False)

        row = rows[0]
        preferred = (row.get("C_PREFERRED_CUST_FLAG") == "Y")
        tier = "Silver" if preferred else "Bronze"

        first = row.get("C_FIRST_NAME") or ""
        last  = row.get("C_LAST_NAME")  or ""

        customer = CustomerLookupResult(
            sk=row["C_CUSTOMER_SK"],
            firstName=first,
            lastName=last,
            name=f"{first} {last}".strip(),
            email=row["C_EMAIL_ADDRESS"],
            preferred=preferred,
            tier=tier,
        )

        return CustomerLookupResponse(found=True, customer=customer)

    except Exception as exc:
        logger.error("[GET /api/customers] ERROR: %s", exc)
        raise HTTPException(status_code=500, detail=f"Customer lookup failed: {exc}") from exc
