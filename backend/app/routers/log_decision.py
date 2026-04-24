# app/routers/log_decision.py
"""
POST /api/returns/log_decision

Logs the agent's final decision on a return after assessment is complete.
Inserts the decision into a Snowflake table for tracking and analytics.
"""
from __future__ import annotations
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import snowflake.connector

from app.config import get_settings

logger = logging.getLogger("routers.log_decision")
settings = get_settings()

router = APIRouter(prefix="/api/returns", tags=["returns"])


# ── Request/Response Models ───────────────────────────────────────────────

class LogDecisionRequest(BaseModel):
    """
    Frontend sends the agent's decision after assessment
    """
    ticket_number: str = Field("", alias="ticketNumber")

    # Customer info
    customer_email: str
    customer_name: str = ""
    customer_tier: str = "Bronze"
    
    # Item info
    item_sk: int
    item_name: str = ""
    item_category: str = ""
    
    # Return details
    return_qty: int = 1
    packaging_condition: str
    packaging_factor: float
    return_amt: float
    net_loss: float
    
    # Assessment results
    assessment_confidence: float
    assessment_complete: bool
    questions_validated: int = 0  # How many of 5 were validated
    
    # Agent's final decision
    decision: str = Field(..., description="'approved' or 'denied'")
    decision_note: str = ""  # Optional note from agent
    
    # Assessment summary from endpoint
    assessment_summary: str = ""


class LogDecisionResponse(BaseModel):
    """Confirmation that decision was logged"""
    success: bool
    decision_id: str
    logged_at: str
    decision: str


# ── Endpoint ──────────────────────────────────────────────────────────────

@router.post(
    "/log_decision",
    response_model=LogDecisionResponse,
    summary="Log return decision after assessment"
)
async def log_decision(payload: LogDecisionRequest) -> LogDecisionResponse:
    """
    Logs the agent's approve/deny decision to Snowflake.
    
    Creates a record in RETURN_DECISIONS table tracking:
    - What was decided (approved/denied)
    - Assessment confidence and validation status
    - Financial impact (return_amt, net_loss)
    - Timestamp and agent notes
    """
    
    logger.info("=" * 70)
    logger.info("LOGGING RETURN DECISION")
    logger.info(f"  Decision: {payload.decision.upper()}")
    logger.info(f"  Customer: {payload.customer_email}")
    logger.info(f"  Item SK: {payload.item_sk}")
    logger.info(f"  Return Amt: ${payload.return_amt:.2f}")
    logger.info(f"  Net Loss: ${payload.net_loss:.2f}")
    logger.info(f"  Confidence: {payload.assessment_confidence:.2f}")
    logger.info("=" * 70)
    
    if payload.decision not in ("approved", "denied"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision: '{payload.decision}'. Must be 'approved' or 'denied'."
        )
    
    # ── Connect to Snowflake ──────────────────────────────────────────────
    try:
        conn = snowflake.connector.connect(
            account=settings.SNOWFLAKE_ACCOUNT,
            user=settings.SNOWFLAKE_USERNAME,
            password=settings.SNOWFLAKE_PASSWORD,
            warehouse=settings.SNOWFLAKE_WAREHOUSE,
            database=settings.SNOWFLAKE_DATABASE,
            schema=settings.SNOWFLAKE_SCHEMA,
            role=settings.SNOWFLAKE_ROLE,
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            ALTER TABLE IF EXISTS RETURN_DECISIONS
            ADD COLUMN IF NOT EXISTS SR_TICKET_NUMBER VARCHAR(50)
            """
        )
        
        # ── Create table if not exists ────────────────────────────────────
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS RETURN_DECISIONS (
            DECISION_ID VARCHAR(50) PRIMARY KEY,
            LOGGED_AT TIMESTAMP_NTZ,
            SR_TICKET_NUMBER VARCHAR(50),
            
            -- Customer
            CUSTOMER_EMAIL VARCHAR(255),
            CUSTOMER_NAME VARCHAR(255),
            CUSTOMER_TIER VARCHAR(50),
            
            -- Item
            ITEM_SK INTEGER,
            ITEM_NAME VARCHAR(500),
            ITEM_CATEGORY VARCHAR(255),
            
            -- Return details
            RETURN_QTY INTEGER,
            PACKAGING_CONDITION VARCHAR(50),
            PACKAGING_FACTOR NUMBER(4,2),
            RETURN_AMT NUMBER(10,2),
            NET_LOSS NUMBER(10,2),
            
            -- Assessment
            ASSESSMENT_CONFIDENCE NUMBER(4,3),
            ASSESSMENT_COMPLETE BOOLEAN,
            QUESTIONS_VALIDATED INTEGER,
            ASSESSMENT_SUMMARY VARCHAR(2000),
            
            -- Decision
            DECISION VARCHAR(20),
            DECISION_NOTE VARCHAR(1000)
        )
        """
        cursor.execute(create_table_sql)
        
        # ── Generate decision ID ──────────────────────────────────────────
        decision_id = f"RD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{payload.item_sk}"
        logged_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # ── Insert decision record ────────────────────────────────────────
        insert_sql = """
        INSERT INTO RETURN_DECISIONS (
            DECISION_ID, LOGGED_AT,
            SR_TICKET_NUMBER,
            CUSTOMER_EMAIL, CUSTOMER_NAME, CUSTOMER_TIER,
            ITEM_SK, ITEM_NAME, ITEM_CATEGORY,
            RETURN_QTY, PACKAGING_CONDITION, PACKAGING_FACTOR,
            RETURN_AMT, NET_LOSS,
            ASSESSMENT_CONFIDENCE, ASSESSMENT_COMPLETE, QUESTIONS_VALIDATED,
            ASSESSMENT_SUMMARY,
            DECISION, DECISION_NOTE
        ) VALUES (
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s,
            %s,
            %s, %s
        )
        """
        
        cursor.execute(insert_sql, (
            decision_id, logged_at,
            payload.ticket_number or None,
            payload.customer_email, payload.customer_name, payload.customer_tier,
            payload.item_sk, payload.item_name, payload.item_category,
            payload.return_qty, payload.packaging_condition, payload.packaging_factor,
            payload.return_amt, payload.net_loss,
            payload.assessment_confidence, payload.assessment_complete, payload.questions_validated,
            payload.assessment_summary,
            payload.decision, payload.decision_note,
        ))
        
        conn.commit()
        logger.info(f"✓ Logged decision {decision_id} to RETURN_DECISIONS table")
        
    except Exception as exc:
        logger.error(f"Failed to log decision to Snowflake: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to log decision: {exc}"
        ) from exc
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return LogDecisionResponse(
        success=True,
        decision_id=decision_id,
        logged_at=logged_at,
        decision=payload.decision,
    )
