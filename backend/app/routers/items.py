# app/routers/items.py
"""
GET /api/items?sk=<I_ITEM_SK>

Looks up a single item by its actual I_ITEM_SK value and returns all
display fields plus its I_RN rank position.

The rank (I_RN) is what must be stored in SR_ITEM_SK on STORE_RETURNS
so the listing query's ROW_NUMBER() JOIN resolves the item correctly.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import run_query

logger = logging.getLogger("routers.items")

router = APIRouter(prefix="/api/items", tags=["items"])


# ── Response schema ───────────────────────────────────────────────────────

class ItemDetail(BaseModel):
    sk: int                   # I_ITEM_SK  (actual PK)
    rn: int                   # I_RN       (rank — what to store in SR_ITEM_SK)
    item_id: str
    name: str
    brand: str
    category: str
    category_full: str
    cls: str                  # I_CLASS  ('class' is reserved in Python)
    price: str                # I_CURRENT_PRICE as formatted string
    list_price: str           # I_LIST_PRICE
    desc: str
    url: str
    package_size: str
    item_number: str


class ItemLookupResponse(BaseModel):
    found: bool
    item: ItemDetail | None = None


# ── Endpoint ──────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=ItemLookupResponse,
    summary="Look up an item by I_ITEM_SK",
)
async def lookup_item(
    sk: int = Query(..., description="The I_ITEM_SK value of the item to look up"),
) -> ItemLookupResponse:

    try:
        # Fetch the item plus its rank position in one query.
        # The subquery mirrors exactly what the ticket listing query uses
        # so the returned rn value is always in sync.
        rows = run_query(
            """
            SELECT
                ranked.I_ITEM_SK,
                ranked.I_RN,
                ranked.I_ITEM_ID,
                ranked.I_PRODUCT_NAME,
                ranked.I_BRAND,
                ranked.I_CATEGORY,
                ranked.I_CATEGORY_FULL,
                ranked.I_CLASS,
                ranked.I_CURRENT_PRICE,
                ranked.I_LIST_PRICE,
                ranked.I_ITEM_DESC,
                ranked.I_PRODUCT_URL,
                ranked.I_PACKAGE_SIZE,
                ranked.I_ITEM_NUMBER
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (ORDER BY I_ITEM_SK) AS I_RN
                FROM SYNTHETIC_COMPANYDB.COMPANY.ITEM
                WHERE I_AVAILABLE = TRUE
            ) ranked
            WHERE ranked.I_ITEM_SK = %s
            LIMIT 1
            """,
            (sk,),
        )

        if not rows:
            return ItemLookupResponse(found=False)

        r = rows[0]

        item = ItemDetail(
            sk=r["I_ITEM_SK"],
            rn=r["I_RN"],
            item_id=r.get("I_ITEM_ID") or "",
            name=r.get("I_PRODUCT_NAME") or "",
            brand=r.get("I_BRAND") or "",
            category=r.get("I_CATEGORY") or "",
            category_full=r.get("I_CATEGORY_FULL") or r.get("I_CATEGORY") or "",
            cls=r.get("I_CLASS") or "",
            price=f"{float(r.get('I_CURRENT_PRICE') or 0):.2f}",
            list_price=f"{float(r.get('I_LIST_PRICE') or 0):.2f}",
            desc=(r.get("I_ITEM_DESC") or "")[:400],
            url=r.get("I_PRODUCT_URL") or "",
            package_size=r.get("I_PACKAGE_SIZE") or "",
            item_number=r.get("I_ITEM_NUMBER") or "",
        )

        return ItemLookupResponse(found=True, item=item)

    except Exception as exc:
        logger.error("[GET /api/items] ERROR: %s", exc)
        raise HTTPException(status_code=500, detail=f"Item lookup failed: {exc}") from exc
