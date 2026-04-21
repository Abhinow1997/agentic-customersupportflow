"""
GET /api/store-sales?email=...

Returns STORE_SALES rows for a customer email using the canonical validation
query shared with the research flow.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.store_sales_lookup import lookup_store_sales_by_customer_email

logger = logging.getLogger("routers.store_sales")

router = APIRouter(prefix="/api/store-sales", tags=["store-sales"])


class StoreSalesRow(BaseModel):
    customer_email: str = Field(..., alias="customerEmail")
    first_name: str = Field("", alias="firstName")
    last_name: str = Field("", alias="lastName")
    item_sk: int = Field(..., alias="itemSk")
    item_name: str = Field("", alias="itemName")
    item_category: str = Field("", alias="itemCategory")
    ticket_number: int = Field(..., alias="ticketNumber")
    quantity: int = 0
    sales_price: float = Field(0.0, alias="salesPrice")
    ext_sales_price: float = Field(0.0, alias="extSalesPrice")

    model_config = {"populate_by_name": True}


class StoreSalesLookupResponse(BaseModel):
    found: bool
    valid: bool
    note: str
    confidence: float
    row_count: int = Field(0, alias="rowCount")
    rows: list[StoreSalesRow] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


@router.get(
    "",
    response_model=StoreSalesLookupResponse,
    summary="Look up STORE_SALES rows by customer email",
)
async def lookup_store_sales(
    email: str = Query(..., description="Customer email address"),
) -> StoreSalesLookupResponse:
    if not email.strip():
        raise HTTPException(status_code=400, detail="email query parameter is required")

    try:
        result = lookup_store_sales_by_customer_email(email)
        return StoreSalesLookupResponse(
            found=result.get("found", False),
            valid=result.get("valid", False),
            note=result.get("note", ""),
            confidence=float(result.get("confidence", 0.0)),
            rowCount=int(result.get("row_count", 0)),
            rows=[StoreSalesRow(**row) for row in result.get("rows", [])],
        )
    except Exception as exc:
        logger.error("[GET /api/store-sales] ERROR: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"STORE_SALES lookup failed: {exc}") from exc
