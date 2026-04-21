"""
Snowflake helper for validating ITEM facts by item SK.
"""
from __future__ import annotations

import logging
from typing import Any

from app.db import run_query

logger = logging.getLogger(__name__)


def lookup_item_by_sk(item_sk: int) -> dict[str, Any]:
    """
    Return the item row for a given item SK.
    """
    try:
        rows = run_query(
            """
            SELECT
                I_ITEM_SK,
                I_PRODUCT_NAME,
                I_CATEGORY,
                I_CATEGORY_FULL,
                I_CLASS,
                I_BRAND,
                I_CURRENT_PRICE
            FROM SYNTHETIC_COMPANYDB.COMPANY.ITEM
            WHERE I_ITEM_SK = %s
            LIMIT 1
            """,
            (item_sk,),
        )

        if not rows:
            return {
                "found": False,
                "valid": False,
                "compliance_status": "missing",
                "source_name": "ITEM",
                "exact_issue": f"No ITEM row found for item_sk={item_sk}.",
                "evidence": "",
                "note": f"No ITEM row found for item_sk={item_sk}.",
                "confidence": 0.25,
            }

        row = rows[0]
        return {
            "found": True,
            "valid": True,
            "compliance_status": "compliant",
            "source_name": "ITEM",
            "exact_issue": "Confirmed ITEM metadata for requested item_sk.",
            "evidence": (
                f"{row.get('I_PRODUCT_NAME')} in category {row.get('I_CATEGORY')} "
                f"with class {row.get('I_CLASS')}."
            ),
            "note": "Confirmed ITEM metadata for requested item_sk.",
            "confidence": 0.95,
            "item_sk": row.get("I_ITEM_SK"),
            "item_name": row.get("I_PRODUCT_NAME"),
            "item_category": row.get("I_CATEGORY"),
            "item_category_full": row.get("I_CATEGORY_FULL"),
            "item_class": row.get("I_CLASS"),
            "brand": row.get("I_BRAND"),
            "price": row.get("I_CURRENT_PRICE"),
        }
    except Exception as exc:
        logger.error("ITEM lookup failed: %s", exc, exc_info=True)
        return {
            "found": False,
            "valid": False,
            "compliance_status": "error",
            "source_name": "ITEM",
            "exact_issue": f"Technical failure during ITEM lookup: {exc}",
            "evidence": "",
            "note": f"Technical failure during ITEM lookup: {exc}",
            "confidence": 0.0,
        }
