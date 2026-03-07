# app/routers/reasons.py
"""
GET /api/reasons

Returns all return reasons from the Snowflake REASON table,
ordered by R_REASON_SK ascending.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException

from app.db import run_query
from app.models import ReasonsResponse, ReasonModel

logger = logging.getLogger("routers.reasons")

router = APIRouter(prefix="/api/reasons", tags=["reasons"])


@router.get(
    "",
    response_model=ReasonsResponse,
    summary="List all return reasons from Snowflake",
)
async def list_reasons() -> ReasonsResponse:
    try:
        rows = run_query(
            """
            SELECT
                R_REASON_SK,
                R_REASON_ID,
                R_REASON_DESC
            FROM SYNTHETIC_COMPANYDB.COMPANY.REASON
            ORDER BY R_REASON_SK ASC
            """
        )

        reasons = [
            ReasonModel(
                id=row["R_REASON_SK"],
                code=row["R_REASON_ID"],
                desc=row["R_REASON_DESC"],
            )
            for row in rows
        ]

        return ReasonsResponse(reasons=reasons)

    except Exception as exc:
        logger.error("[GET /api/reasons] ERROR: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to fetch reasons: {exc}") from exc
