"""
Enquiry workflow endpoints.

POST /api/enquiry/analyze
  - classifies the incoming enquiry
  - drafts an email response
  - returns reviewable suggestions for the frontend

POST /api/enquiry/create
  - inserts the validated enquiry into ENQUIRY_TICKETS
"""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.agents.response_agent import analyze_enquiry_message
from app.db import get_connection, run_query
from app.models import (
    EnquiryAnalyzeRequest,
    EnquiryAnalyzeResponse,
    EnquiryCreateRequest,
    EnquiryCreateResponse,
)

logger = logging.getLogger("routers.enquiries")

router = APIRouter(prefix="/api/enquiry", tags=["enquiry"])


@router.post(
    "/analyze",
    response_model=EnquiryAnalyzeResponse,
    summary="Classify and draft an enquiry response",
)
async def analyze_enquiry(payload: EnquiryAnalyzeRequest) -> EnquiryAnalyzeResponse:
    try:
        result = analyze_enquiry_message(payload.model_dump())
        return EnquiryAnalyzeResponse.model_validate(result)
    except Exception as exc:
        logger.error("[POST /api/enquiry/analyze] ERROR: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze enquiry: {exc}") from exc


@router.post(
    "/create",
    response_model=EnquiryCreateResponse,
    summary="Create an enquiry ticket in Snowflake",
)
async def create_enquiry(payload: EnquiryCreateRequest) -> EnquiryCreateResponse:
    if not payload.customer.email.strip():
        raise HTTPException(status_code=400, detail="Customer email is required")
    if not payload.subject.strip():
        raise HTTPException(status_code=400, detail="Subject is required")
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Enquiry body is required")

    classification = payload.classification
    customer_name = payload.customer.name.strip() or payload.customer.email.strip()
    subject = payload.draft_subject.strip() or payload.subject.strip()
    body_text = payload.body.strip()
    draft_response = payload.draft_response.strip()
    ai_summary = payload.ai_summary.strip()
    status = payload.status.strip() or "Open"
    priority = classification.priority.strip() or "Medium"
    ticket_number = _generate_ticket_number()
    ticket_id = ticket_number

    customer_sk = payload.customer.sk
    if customer_sk is None:
        try:
            rows = run_query(
                """
                SELECT C_CUSTOMER_SK
                FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER
                WHERE LOWER(C_EMAIL_ADDRESS) = LOWER(%s)
                LIMIT 1
                """,
                (payload.customer.email.strip(),),
            )
            if rows:
                customer_sk = rows[0]["C_CUSTOMER_SK"]
        except Exception as exc:
            logger.warning("[POST /api/enquiry/create] Customer lookup failed: %s", exc)

    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS (
                ENQ_TICKET_NUMBER,
                ENQ_CUSTOMER_SK,
                ENQ_CUSTOMER_EMAIL,
                ENQ_CUSTOMER_NAME,
                ENQ_SUBJECT,
                ENQ_BODY,
                ENQ_CHANNEL,
                ENQ_CATEGORY,
                ENQ_SUBCATEGORY,
                ENQ_STATUS,
                ENQ_PRIORITY,
                ENQ_ASSIGNED_TO,
                ENQ_RESOLUTION,
                ENQ_RESOLVED_AT,
                ENQ_RESOLUTION_TIME_MINUTES,
                ENQ_CREATED_AT,
                ENQ_UPDATED_AT,
                ENQ_SENTIMENT_SCORE,
                ENQ_SENTIMENT_LABEL,
                ENQ_URGENCY_SCORE,
                ENQ_CLASSIFICATION_CONFIDENCE,
                ENQ_EMBEDDING,
                ENQ_AI_SUMMARY,
                ENQ_SUGGESTED_RESPONSE,
                ENQ_VOICEMAIL_S3_KEY,
                ENQ_VOICEMAIL_DURATION_SEC,
                ENQ_EMAIL_THREAD_ID
            ) VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NULL,
                NULL,
                CURRENT_TIMESTAMP(),
                CURRENT_TIMESTAMP(),
                %s,
                %s,
                %s,
                %s,
                NULL,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                ticket_number,
                customer_sk,
                payload.customer.email.strip(),
                customer_name,
                subject,
                body_text,
                payload.channel,
                classification.category,
                classification.subcategory,
                status,
                priority,
                payload.assigned_to.strip() or None,
                draft_response or None,
                float(classification.sentiment_score or 0.0),
                classification.sentiment_label,
                int(classification.urgency_score or 0),
                float(classification.confidence or 0.0),
                ai_summary or None,
                draft_response or None,
                payload.voicemail_s3_key.strip() or None,
                float(payload.voicemail_duration_sec or 0.0),
                payload.email_thread_id.strip() or None,
            ),
        )
        conn.commit()
    except Exception as exc:
        logger.error("[POST /api/enquiry/create] ERROR: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create enquiry ticket: {exc}") from exc
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

    return EnquiryCreateResponse(
        ok=True,
        ticketId=ticket_id,
        ticketNumber=ticket_number,
        message="Enquiry ticket created successfully",
    )


def _generate_ticket_number() -> str:
    ts_part = str(int(time.time()))
    rand_part = str(random.randint(0, 99)).zfill(2)
    return f"ENQ-{ts_part}{rand_part}"
