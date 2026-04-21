# app/routers/access_item_return.py
"""
POST /api/access_item_return

Dewey-inspired adaptive triage system with multi-agent communication.

Flow:
1. Researcher Agent receives item + packaging condition from frontend
2. Researcher formulates answers to 5 critical questions
3. For each answer, Researcher communicates with Policy Agent for validation
4. Policy Agent validates against scraped policies
5. Researcher adjusts based on validation feedback
6. Final assessment returned to frontend

This implements adaptive scaffolding - the agents learn optimal question-answering
sequences through policy gradients (RL component to be added).
"""
from __future__ import annotations
import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.researcher_agent import ResearcherAgent
from app.agents.policy_agent import PolicyAgent

logger = logging.getLogger("routers.access_item_return")

router = APIRouter(prefix="/api", tags=["item_return"])


# ── Request/Response Models ───────────────────────────────────────────────

class AccessItemReturnRequest(BaseModel):
    """
    Frontend sends:
    - Item SK and price
    - Return quantity
    - Packaging condition assessment
    """
    item_sk: int = Field(..., alias="item_sk")
    price: str
    return_qty: int = Field(1, alias="return_qty")
    packaging_condition: str = Field(..., alias="packaging_condition")
    factor: float
    customer_email: str = Field(..., alias="customer_email")
    customer_remarks: str = Field("", alias="customer_remarks")
    return_reason: str = Field("", alias="return_reason")
    follow_up_answers: list[dict] = Field(default_factory=list, alias="follow_up_answers")

    model_config = {"populate_by_name": True}


class QuestionAnswer(BaseModel):
    """Single question-answer pair with validation status"""
    question: str
    answer: str
    confidence: float = 0.0
    answer_source: str = Field("", alias="answerSource")
    validated: bool = False
    validation_note: str = ""
    exact_issue: str = ""
    source_checks: list[dict] = Field(default_factory=list, alias="sourceChecks")


class ResearcherPolicyExchange(BaseModel):
    """Captures one round of Researcher -> Policy communication"""
    question_id: int
    question: str
    researcher_answer: str
    policy_query: str
    policy_validation: dict
    final_answer: str
    confidence: float
    exact_issue: str = ""
    source_checks: list[dict] = Field(default_factory=list, alias="sourceChecks")


class AccessItemReturnResponse(BaseModel):
    """
    Returns:
    - Answers to the 5 critical questions
    - Communication history between Researcher and Policy agents
    - Final assessment metrics
    """
    item_sk: int
    packaging_condition: str
    
    # The 5 critical questions with answers
    questions: list[QuestionAnswer]
    
    # Agent communication history
    researcher_policy_exchanges: list[ResearcherPolicyExchange] = Field(
        default_factory=list, 
        alias="researcherPolicyExchanges"
    )

    sales_history: dict = Field(default_factory=dict, alias="salesHistory")
    sales_validation: dict = Field(default_factory=dict, alias="salesValidation")
    item_validation: dict = Field(default_factory=dict, alias="itemValidation")
    resolved_context: dict = Field(default_factory=dict, alias="resolvedContext")
    remarks_analysis: dict = Field(default_factory=dict, alias="remarksAnalysis")
    awaiting_follow_up: bool = Field(False, alias="awaitingFollowUp")
    follow_up_questions: list[dict] = Field(default_factory=list, alias="followUpQuestions")
    
    # Financial assessment
    return_amt: float = Field(..., alias="returnAmt")
    net_loss: float = Field(..., alias="netLoss")
    
    # Overall assessment
    assessment_complete: bool = Field(..., alias="assessmentComplete")
    assessment_confidence: float = Field(0.0, alias="assessmentConfidence")
    
    model_config = {"populate_by_name": True}


# ── Endpoint ──────────────────────────────────────────────────────────────

@router.post(
    "/access_item_return",
    response_model=AccessItemReturnResponse,
    summary="Adaptive triage assessment with Researcher-Policy agent communication",
)
async def access_item_return(payload: AccessItemReturnRequest) -> AccessItemReturnResponse:
    """
    Dewey-inspired multi-agent assessment system.
    
    The Researcher Agent gathers information to answer 5 critical questions,
    communicating with the Policy Agent for validation at each step.
    """
    
    logger.info("=" * 70)
    logger.info("ADAPTIVE TRIAGE START")
    logger.info(f"  Item SK: {payload.item_sk}")
    logger.info(f"  Customer Email: {payload.customer_email}")
    logger.info(f"  Packaging: {payload.packaging_condition} (factor: {payload.factor})")
    logger.info(f"  Return Qty: {payload.return_qty} @ ${payload.price}")
    logger.info("=" * 70)
    
    # ── Initialize agents ─────────────────────────────────────────────────
    researcher = ResearcherAgent()
    policy_validator = PolicyAgent()
    
    # ── Build initial context from frontend data ──────────────────────────
    item_context = {
        "item_sk": payload.item_sk,
        "price": float(payload.price),
        "return_qty": payload.return_qty,
        "packaging_condition": payload.packaging_condition,
        "packaging_factor": payload.factor,
        "customer_remarks": payload.customer_remarks,
        "return_reason": payload.return_reason,
    }
    
    # ── Researcher gathers answers through Policy Agent communication ─────
    try:
        # This is where the multi-turn communication happens
        research_result = await researcher.investigate_return(
            item_context=item_context,
            policy_agent=policy_validator,
            customer_email=payload.customer_email,
            customer_remarks=payload.customer_remarks or payload.return_reason,
            follow_up_answers=payload.follow_up_answers,
        )
        
    except Exception as exc:
        logger.error(f"Research investigation failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Researcher agent failed: {exc}"
        ) from exc
    
    # ── Calculate financials ──────────────────────────────────────────────
    return_amt = float(payload.price) * payload.return_qty
    net_loss = return_amt * payload.factor
    
    # ── Log communication exchanges ───────────────────────────────────────
    logger.info("")
    logger.info("--- RESEARCHER-POLICY COMMUNICATION ---")
    for i, exchange in enumerate(research_result["exchanges"], 1):
        logger.info(f"  [{i}] Question: {exchange['question'][:80]}")
        logger.info(f"      Researcher: {exchange['researcher_answer'][:80]}")
        logger.info(f"      Policy Query: {exchange['policy_query'][:60]}")
        logger.info(f"      Validated: {exchange['policy_validation'].get('valid', False)}")
        logger.info(f"      Exact Issue: {exchange.get('exact_issue', '')}")
        logger.info(f"      Final: {exchange['final_answer'][:80]}")
        logger.info("")
    
    logger.info("--- FINAL ANSWERS ---")
    for qa in research_result["questions"]:
        logger.info(f"  Q: {qa['question']}")
        logger.info(
            f"  A: {qa['answer']} (confidence: {qa['confidence']:.2f}, "
            f"validated: {qa['validated']})"
        )
        logger.info(f"  Exact Issue: {qa.get('exact_issue', '')}")
        for source_check in qa.get("source_checks", []):
            logger.info(
                "    - %s [%s]: %s",
                source_check.get("source_name", "unknown"),
                source_check.get("status", "unknown"),
                source_check.get("exact_issue", ""),
            )
        logger.info("")

    if research_result.get("remarks_analysis"):
        remarks_analysis = research_result["remarks_analysis"]
        logger.info("--- CUSTOMER REMARKS ANALYSIS ---")
        logger.info(f"  Provided: {remarks_analysis.get('provided', False)}")
        logger.info(f"  Summary: {remarks_analysis.get('summary', '')}")
        logger.info(f"  Covered Questions: {len(remarks_analysis.get('covered_questions', []))}")
        for covered in remarks_analysis.get("covered_questions", []):
            logger.info(
                "    - Q%s: %s | %s",
                covered.get("question_id", "?"),
                covered.get("question", ""),
                covered.get("answer", ""),
            )
        if remarks_analysis.get("follow_up_questions"):
            logger.info("  Follow-up Questions:")
            for follow_up in remarks_analysis["follow_up_questions"]:
                logger.info(f"    - {follow_up}")

    logger.info(f"Assessment Complete: {research_result['assessment_complete']}")
    logger.info(f"Overall Confidence: {research_result['assessment_confidence']:.2f}")
    logger.info("=" * 70)
    
    # ── Build response ────────────────────────────────────────────────────
    response = AccessItemReturnResponse(
        item_sk=payload.item_sk,
        packaging_condition=payload.packaging_condition,
        questions=[QuestionAnswer(**qa) for qa in research_result["questions"]],
        researcherPolicyExchanges=[
            ResearcherPolicyExchange(**ex) for ex in research_result["exchanges"]
        ],
        salesHistory=research_result.get("sales_history", {}),
        salesValidation=research_result.get("sales_validation", {}),
        itemValidation=research_result.get("item_validation", {}),
        resolvedContext=research_result.get("resolved_context", {}),
        remarksAnalysis=research_result.get("remarks_analysis", {}),
        awaitingFollowUp=research_result.get("awaiting_follow_up", False),
        followUpQuestions=research_result.get("follow_up_questions", []),
        returnAmt=return_amt,
        netLoss=net_loss,
        assessmentComplete=research_result["assessment_complete"],
        assessmentConfidence=research_result["assessment_confidence"],
    )

    logger.info("--- FULL ENDPOINT RESPONSE ---")
    logger.info(json.dumps(response.model_dump(by_alias=True), default=str, indent=2))
    logger.info("=" * 70)
    return response
