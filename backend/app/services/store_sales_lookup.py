"""
Snowflake helpers for validating STORE_SALES history.

The return-assessment flow uses these helpers to confirm that a customer email
and item SK actually exist together in sales history, and to surface the most
recent purchase date for the researcher agent.
"""
from __future__ import annotations

import logging
from typing import Any

from app.db import run_query

logger = logging.getLogger(__name__)

def _get_val(row: dict, key: str) -> Any:
    """Helper to safely extract dictionary values regardless of driver case-sensitivity."""
    if not row:
        return None
    for k, v in row.items():
        if k.lower() == key.lower():
            return v
    return None

def lookup_store_sales_by_customer_email(customer_email: str) -> dict[str, Any]:
    """
    Return STORE_SALES rows for a customer email using the canonical sales
    validation query provided by the project.
    """
    if not customer_email.strip():
        return {
            "found": False,
            "valid": False,
            "compliance_status": "missing",
            "source_name": "STORE_SALES",
            "exact_issue": "Customer email is required for STORE_SALES lookup.",
            "evidence": "",
            "note": "Customer email is required for STORE_SALES lookup.",
            "confidence": 0.0,
            "rows": [],
        }

    try:
        rows = run_query(
            """
            SELECT
                c.C_EMAIL_ADDRESS,
                c.C_FIRST_NAME,
                c.C_LAST_NAME,
                i.I_ITEM_SK,
                i.I_PRODUCT_NAME,
                i.I_CATEGORY,
                s.SS_TICKET_NUMBER,
                s.SS_QUANTITY,
                s.SS_SALES_PRICE,
                s.SS_EXT_SALES_PRICE
            FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES s
            JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
                ON s.SS_CUSTOMER_SK = c.C_CUSTOMER_SK
            JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
                ON s.SS_ITEM_SK = i.I_ITEM_SK
            WHERE c.C_EMAIL_ADDRESS = %s
            ORDER BY s.SS_EXT_SALES_PRICE DESC
            """,
            (customer_email.strip(),),
        )

        normalized_rows = [
            {
                "customer_email": _get_val(row, "C_EMAIL_ADDRESS"),
                "first_name": _get_val(row, "C_FIRST_NAME"),
                "last_name": _get_val(row, "C_LAST_NAME"),
                "item_sk": _get_val(row, "I_ITEM_SK"),
                "item_name": _get_val(row, "I_PRODUCT_NAME"),
                "item_category": _get_val(row, "I_CATEGORY"),
                "ticket_number": _get_val(row, "SS_TICKET_NUMBER"),
                "quantity": _get_val(row, "SS_QUANTITY"),
                "sales_price": _get_val(row, "SS_SALES_PRICE"),
                "ext_sales_price": _get_val(row, "SS_EXT_SALES_PRICE"),
            }
            for row in rows
        ]

        return {
            "found": bool(normalized_rows),
            "valid": bool(normalized_rows),
            "compliance_status": "compliant" if normalized_rows else "missing",
            "source_name": "STORE_SALES",
            "exact_issue": (
                "STORE_SALES rows matched the customer email."
                if normalized_rows
                else "No STORE_SALES rows matched this customer email."
            ),
            "evidence": (
                f"{len(normalized_rows)} row(s) returned from STORE_SALES ordered by SS_EXT_SALES_PRICE DESC."
            ),
            "note": (
                "STORE_SALES rows returned for customer email."
                if normalized_rows
                else "No STORE_SALES rows matched this customer email."
            ),
            "confidence": 0.9 if normalized_rows else 0.2,
            "rows": normalized_rows,
            "row_count": len(normalized_rows),
        }

    except Exception as exc:
        logger.error("STORE_SALES lookup failed: %s", exc, exc_info=True)
        return {
            "found": False,
            "valid": False,
            "compliance_status": "error",
            "source_name": "STORE_SALES",
            "exact_issue": f"Technical failure during STORE_SALES lookup: {exc}",
            "evidence": "",
            "note": f"Technical failure during STORE_SALES lookup: {exc}",
            "confidence": 0.0,
            "rows": [],
        }

def lookup_purchase_date_by_item_and_email(
    item_sk: int,
    customer_email: str,
) -> dict[str, Any]:
    """
    Find the most recent purchase date for a given item + customer email.
    """
    if not customer_email.strip():
        return {
            "found": False,
            "valid": False,
            "compliance_status": "missing",
            "source_name": "STORE_SALES",
            "exact_issue": "Customer email is required for STORE_SALES validation.",
            "evidence": "",
            "note": "Customer email is required for STORE_SALES validation.",
            "confidence": 0.0,
        }

    try:
        rows = run_query(
            """
            SELECT
                ss.SS_TICKET_NUMBER,
                ss.SS_ITEM_SK,
                ss.SS_CUSTOMER_SK,
                ss.SS_QUANTITY,
                ss.SS_SALES_PRICE,
                ss.SS_SOLD_DATE_SK,
                d.D_DATE AS PURCHASE_DATE,
                c.C_EMAIL_ADDRESS,
                c.C_CUSTOMER_SK,
                i.I_PRODUCT_NAME
            FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
                INNER JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
                    ON c.C_CUSTOMER_SK = ss.SS_CUSTOMER_SK
                INNER JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
                    ON i.I_ITEM_SK = ss.SS_ITEM_SK
                LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.DATE_DIM d
                    ON d.D_DATE_SK = ss.SS_SOLD_DATE_SK
            WHERE LOWER(c.C_EMAIL_ADDRESS) = LOWER(%s)
              AND ss.SS_ITEM_SK = %s
            ORDER BY ss.SS_SOLD_DATE_SK DESC, ss.SS_TICKET_NUMBER DESC
            LIMIT 1
            """,
            (customer_email.strip(), item_sk),
        )

        if not rows:
            return {
                "found": False,
                "valid": False,
                "compliance_status": "missing",
                "source_name": "STORE_SALES",
                "exact_issue": "No matching STORE_SALES row was found for this item and customer email.",
                "evidence": "",
                "note": "No matching STORE_SALES row was found for this item and customer email.",
                "confidence": 0.25,
            }

        row = rows[0]
        
        # Safely extract variables avoiding casing issues
        purchase_date = _get_val(row, "PURCHASE_DATE")
        sold_date_sk = _get_val(row, "SS_SOLD_DATE_SK")
        ticket_number = _get_val(row, "SS_TICKET_NUMBER")
        customer_sk = _get_val(row, "SS_CUSTOMER_SK")
        c_email_address = _get_val(row, "C_EMAIL_ADDRESS")
        ss_item_sk = _get_val(row, "SS_ITEM_SK")
        i_product_name = _get_val(row, "I_PRODUCT_NAME")
        ss_quantity = _get_val(row, "SS_QUANTITY")
        ss_sales_price = _get_val(row, "SS_SALES_PRICE")

        if hasattr(purchase_date, "isoformat"):
            purchase_date_str = purchase_date.isoformat()
            date_issue = "Confirmed purchase date from DATE_DIM."
        elif purchase_date is not None:
            purchase_date_str = str(purchase_date)
            date_issue = "Confirmed purchase date from DATE_DIM."
        else:
            purchase_date_str = f"DATE_SK:{sold_date_sk}" if sold_date_sk is not None else ""
            date_issue = "DATE_DIM lookup was unavailable; using SS_SOLD_DATE_SK surrogate."

        return {
            "found": True,
            "valid": True,
            "compliance_status": "compliant",
            "source_name": "STORE_SALES",
            "exact_issue": "Confirmed item/customer match in STORE_SALES.",
            "evidence": (
                f"Ticket {ticket_number} with item SK {ss_item_sk} "
                f"and purchase date {purchase_date_str}. {date_issue}"
            ),
            "note": "Confirmed item/customer match in STORE_SALES.",
            "confidence": 0.95,
            "purchase_date": purchase_date_str,
            "ticket_number": ticket_number,
            "sold_date_sk": sold_date_sk,
            "customer_sk": customer_sk,
            "customer_email": c_email_address,
            "item_sk": ss_item_sk,
            "item_name": i_product_name,
            "quantity": ss_quantity,
            "sales_price": ss_sales_price,
        }

    except Exception as exc:
        logger.error("STORE_SALES lookup failed: %s", exc, exc_info=True)
        return {
            "found": False,
            "valid": False,
            "compliance_status": "error",
            "source_name": "STORE_SALES",
            "exact_issue": f"Technical failure during STORE_SALES validation: {exc}",
            "evidence": "",
            "note": f"Technical failure during STORE_SALES validation: {exc}",
            "confidence": 0.0,
        }