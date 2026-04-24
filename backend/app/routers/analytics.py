# app/routers/analytics.py
"""
GET /api/analytics/dashboard

Returns aggregated analytics data from Snowflake for the frontend dashboard.
Includes executive KPIs, customer support health, and top performing categories.
"""
from __future__ import annotations
import logging
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.db import run_query

logger = logging.getLogger("routers.analytics")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# ==========================================
# Models (Move to app/models.py if desired)
# ==========================================

class DashboardKPIs(BaseModel):
    totalRevenue: float
    netProfit: float
    returnRate: float
    openTickets: int

class SupportHealthRow(BaseModel):
    enqCategory: str
    enqPriority: str
    ticketCount: int
    avgSentiment: float
    negativeTickets: int
    avgResolutionMin: float
    openCount: int

class TopCategory(BaseModel):
    name: str
    revenue: float
    margin: float

class DashboardResponse(BaseModel):
    kpis: DashboardKPIs
    supportHealth: List[SupportHealthRow]
    topCategories: List[TopCategory]

# ==========================================
# Routes
# ==========================================

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get analytics dashboard metrics from Snowflake",
)
async def get_dashboard() -> DashboardResponse:
    try:
        # 1. Fetch KPIs (Combined into a single query for efficiency)
        kpi_rows = run_query(
            """
            SELECT
                (SELECT SUM(SS_NET_PAID) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES) AS total_revenue,
                (SELECT SUM(SS_NET_PROFIT) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES) AS net_profit,
                (SELECT ROUND((SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS) * 100.0
                    / NULLIF((SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES), 0), 2)) AS return_rate,
                (SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS WHERE ENQ_STATUS = 'Open') AS open_tickets
            """
        )
        
        # 2. Fetch Customer Support Health (EDA)
        support_health_rows = run_query(
            """
            SELECT
                ENQ_CATEGORY,
                ENQ_PRIORITY,
                COUNT(*) AS ticket_count,
                ROUND(AVG(ENQ_SENTIMENT_SCORE), 3) AS avg_sentiment,
                SUM(CASE WHEN ENQ_SENTIMENT_LABEL = 'Negative' THEN 1 ELSE 0 END) AS negative_tickets,
                ROUND(AVG(ENQ_RESOLUTION_TIME_MINUTES), 2) AS avg_resolution_min,
                SUM(CASE WHEN ENQ_STATUS = 'Open' THEN 1 ELSE 0 END) AS open_count
            FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
            GROUP BY ENQ_CATEGORY, ENQ_PRIORITY
            ORDER BY ticket_count DESC
            LIMIT 6
            """
        )

        # 3. Fetch Top Categories (Q4 from EDA)
        categories_rows = run_query(
            """
            SELECT
                i.I_CATEGORY AS category_name,
                SUM(ss.SS_NET_PAID) AS revenue,
                (SUM(ss.SS_NET_PROFIT) * 100.0 / NULLIF(SUM(ss.SS_NET_PAID), 0)) AS profit_margin_pct
            FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
            JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
                ON ss.SS_ITEM_SK = i.I_ITEM_SK
            GROUP BY i.I_CATEGORY
            ORDER BY revenue DESC
            LIMIT 5
            """
        )

        # Safely extract KPI data, defaulting to 0 if none is returned
        kpi_data = kpi_rows[0] if kpi_rows else {}
        
        # Map SQL results to Pydantic models. 
        # Note: Keys are typically uppercase when returned from Snowflake via dict cursor.
        kpis = DashboardKPIs(
            totalRevenue=float(kpi_data.get("TOTAL_REVENUE") or 0.0),
            netProfit=float(kpi_data.get("NET_PROFIT") or 0.0),
            returnRate=float(kpi_data.get("RETURN_RATE") or 0.0),
            openTickets=int(kpi_data.get("OPEN_TICKETS") or 0)
        )

        support_health = [
            SupportHealthRow(
                enqCategory=str(row.get("ENQ_CATEGORY", "Unknown")),
                enqPriority=str(row.get("ENQ_PRIORITY", "Unknown")),
                ticketCount=int(row.get("TICKET_COUNT") or 0),
                avgSentiment=float(row.get("AVG_SENTIMENT") or 0.0),
                negativeTickets=int(row.get("NEGATIVE_TICKETS") or 0),
                avgResolutionMin=float(row.get("AVG_RESOLUTION_MIN") or 0.0),
                openCount=int(row.get("OPEN_COUNT") or 0),
            )
            for row in support_health_rows
        ]

        if not support_health:
            logger.warning(
                "[GET /api/analytics/dashboard] ENQUIRY_TICKETS returned no rows for support health"
            )

        top_categories = [
            TopCategory(
                name=str(row.get("CATEGORY_NAME", "Unknown")),
                revenue=float(row.get("REVENUE") or 0.0),
                margin=round(float(row.get("PROFIT_MARGIN_PCT") or 0.0), 1)
            )
            for row in categories_rows
        ]

        return DashboardResponse(
            kpis=kpis,
            supportHealth=support_health,
            topCategories=top_categories
        )

    except Exception as exc:
        logger.error("[GET /api/analytics/dashboard] ERROR: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch analytics dashboard: {exc}"
        ) from exc
