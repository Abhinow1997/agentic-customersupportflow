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

    model_config = {"populate_by_name": True}


class QuestionAnswer(BaseModel):
    """Single question-answer pair with validation status"""
    question: str
    answer: str
    confidence: float = 0.0
    validated: bool = False
    validation_note: str = ""


class ResearcherPolicyExchange(BaseModel):
    """Captures one round of Researcher -> Policy communication"""
    question_id: int
    question: str
    researcher_answer: str
    policy_query: str
    policy_validation: dict
    final_answer: str
    confidence: float


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
    }
    
    # ── Researcher gathers answers through Policy Agent communication ─────
    try:
        # This is where the multi-turn communication happens
        research_result = await researcher.investigate_return(
            item_context=item_context,
            policy_agent=policy_validator
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
        logger.info(f"      Final: {exchange['final_answer'][:80]}")
        logger.info("")
    
    logger.info("--- FINAL ANSWERS ---")
    for qa in research_result["questions"]:
        logger.info(f"  Q: {qa['question']}")
        logger.info(f"  A: {qa['answer']} (confidence: {qa['confidence']:.2f}, validated: {qa['validated']})")
        logger.info("")
    
    logger.info(f"Assessment Complete: {research_result['assessment_complete']}")
    logger.info(f"Overall Confidence: {research_result['assessment_confidence']:.2f}")
    logger.info("=" * 70)
    
    # ── Build response ────────────────────────────────────────────────────
    return AccessItemReturnResponse(
        item_sk=payload.item_sk,
        packaging_condition=payload.packaging_condition,
        questions=[QuestionAnswer(**qa) for qa in research_result["questions"]],
        researcherPolicyExchanges=[
            ResearcherPolicyExchange(**ex) for ex in research_result["exchanges"]
        ],
        returnAmt=return_amt,
        netLoss=net_loss,
        assessmentComplete=research_result["assessment_complete"],
        assessmentConfidence=research_result["assessment_confidence"],
    )
