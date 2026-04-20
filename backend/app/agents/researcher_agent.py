# app/agents/researcher_agent.py
"""
Researcher Agent - Adaptive Information Gathering with LLM Reasoning

Implements Dewey-style scaffolding: learns optimal question-answering sequences
through multi-turn communication with Policy Agent.

Core Responsibilities:
1. Answer 5 critical questions about the return using LLM reasoning
2. Validate answers through Policy Agent communication
3. Refine answers based on policy feedback
4. Track confidence and validation status

Future RL Enhancement:
- Policy gradient learning for optimal question sequencing
- Adaptive information gathering based on customer tier
- Transfer learning across product categories
"""
from __future__ import annotations
import json
import logging
import os
import re
from typing import Any

import litellm
from app.config import get_settings

logger = logging.getLogger("agents.researcher")
settings = get_settings()

# LiteLLM model for reasoning
LLM_MODEL = "gpt-4o-mini"

# System prompt for the Researcher Agent's LLM reasoning
RESEARCHER_SYSTEM_PROMPT = """You are an expert customer support researcher analyzing product returns.

Your job is to reason through a specific question about a return using the available context.

You must provide:
1. A clear, specific answer to the question
2. A confidence score (0.0 to 1.0) for your answer
3. Brief reasoning explaining how you arrived at the answer

Respond with ONLY a valid JSON object - no markdown, no preamble:
{
  "answer": "<your specific answer to the question>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explaining your reasoning>"
}

Guidelines:
- If the context doesn't contain enough information, say "Unknown - requires [what's needed]" and set confidence low (0.2-0.4)
- If you can infer from available context, state your inference clearly and set confidence medium (0.5-0.7)
- If the context directly provides the answer, state it confidently (0.8-1.0)
- Always be specific - avoid vague answers like "it depends" or "maybe"
"""


class ResearcherAgent:
    """
    Multi-agent researcher that gathers return information through
    iterative communication with Policy Agent using LLM reasoning.
    """
    
    # The 5 critical questions every return must answer
    CRITICAL_QUESTIONS = [
        {
            "id": 1,
            "question": "Was this item 'Sold & Shipped by Walmart' or a 'Marketplace' seller?",
            "key": "seller_type",
            "context_keys": ["item_sk"],
        },
        {
            "id": 2,
            "question": "What is the specific purchase or delivery date?",
            "key": "purchase_date",
            "context_keys": ["item_sk"],
        },
        {
            "id": 3,
            "question": "What is the specific category of the item?",
            "key": "item_category",
            "context_keys": ["item_sk"],
        },
        {
            "id": 4,
            "question": "Is the receipt, order number, or the original payment card available and valid?",
            "key": "proof_of_purchase",
            "context_keys": ["item_sk", "packaging_condition"],
        },
        {
            "id": 5,
            "question": "Why is the customer returning the item?",
            "key": "return_reason",
            "context_keys": ["packaging_condition", "packaging_factor"],
        },
    ]
    
    def __init__(self):
        self.communication_history = []
        
    async def investigate_return(
        self, 
        item_context: dict[str, Any],
        policy_agent: Any  # PolicyAgent instance
    ) -> dict[str, Any]:
        """
        Main investigation loop: gather answers to all 5 questions
        through iterative communication with Policy Agent.
        
        Args:
            item_context: {item_sk, price, return_qty, packaging_condition, packaging_factor}
            policy_agent: PolicyAgent instance for validation
            
        Returns:
            {
                "questions": [QuestionAnswer],
                "exchanges": [ResearcherPolicyExchange],
                "assessment_complete": bool,
                "assessment_confidence": float
            }
        """
        logger.info("")
        logger.info("🔬 RESEARCHER AGENT: Beginning investigation")
        logger.info(f"   Context: Item SK {item_context['item_sk']}, "
                   f"Packaging: {item_context['packaging_condition']}")
        
        questions_answered = []
        exchanges = []
        
        # ── Investigate each question sequentially ────────────────────────
        for q_spec in self.CRITICAL_QUESTIONS:
            logger.info("")
            logger.info(f"📋 Question {q_spec['id']}: {q_spec['question']}")
            
            # Step 1: Researcher uses LLM to formulate initial answer
            initial_answer = await self._formulate_answer_llm(q_spec, item_context)
            logger.info(f"   LLM Answer: {initial_answer['answer']}")
            logger.info(f"   LLM Confidence: {initial_answer['confidence']:.2f}")
            logger.info(f"   LLM Reasoning: {initial_answer['reasoning']}")
            
            # Step 2: Ask Policy Agent to validate
            policy_query = self._build_policy_query(q_spec, initial_answer)
            logger.info(f"   Policy Query: {policy_query}")
            
            validation_result = await policy_agent.validate(
                question=q_spec["question"],
                proposed_answer=initial_answer["answer"],
                query=policy_query,
                context=item_context
            )
            
            logger.info(f"   Policy Validation: {validation_result['valid']}")
            if validation_result.get("note"):
                logger.info(f"   Validation Note: {validation_result['note']}")
            
            # Step 3: Researcher adjusts based on validation
            final_answer, final_confidence = self._adjust_answer(
                initial_answer,
                validation_result
            )
            
            logger.info(f"   ✓ Final Answer: {final_answer}")
            logger.info(f"   Final Confidence: {final_confidence:.2f}")
            
            # Record the question-answer
            questions_answered.append({
                "question": q_spec["question"],
                "answer": final_answer,
                "confidence": final_confidence,
                "validated": validation_result["valid"],
                "validation_note": validation_result.get("note", ""),
            })
            
            # Record the communication exchange
            exchanges.append({
                "question_id": q_spec["id"],
                "question": q_spec["question"],
                "researcher_answer": initial_answer["answer"],
                "policy_query": policy_query,
                "policy_validation": validation_result,
                "final_answer": final_answer,
                "confidence": final_confidence,
            })
        
        # ── Compute overall assessment ────────────────────────────────────
        all_validated = all(qa["validated"] for qa in questions_answered)
        avg_confidence = sum(qa["confidence"] for qa in questions_answered) / len(questions_answered)
        
        assessment_complete = all_validated and avg_confidence >= 0.7
        
        logger.info("")
        logger.info(f"🎯 INVESTIGATION COMPLETE")
        logger.info(f"   All Validated: {all_validated}")
        logger.info(f"   Avg Confidence: {avg_confidence:.2f}")
        logger.info(f"   Assessment Complete: {assessment_complete}")
        
        return {
            "questions": questions_answered,
            "exchanges": exchanges,
            "assessment_complete": assessment_complete,
            "assessment_confidence": avg_confidence,
        }
    
    async def _formulate_answer_llm(
        self, 
        q_spec: dict, 
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Use LLM to formulate answer to a question based on available context.
        
        This is where RL will eventually optimize the prompting strategy.
        Currently uses standard LLM reasoning with temperature=0.2.
        """
        question = q_spec["question"]
        q_key = q_spec["key"]
        
        # Build context description for the LLM
        context_str = self._build_context_description(context, q_spec["context_keys"])
        
        # Build the user prompt
        user_prompt = f"""## Question to Answer:
{question}

## Available Context:
{context_str}

Analyze the context and provide your best answer to the question. Remember to include:
- answer: Your specific answer
- confidence: How confident you are (0.0 to 1.0)
- reasoning: One sentence explaining your logic

Respond with ONLY the JSON object."""
        
        try:
            # Call LLM via LiteLLM
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
            
            response = litellm.completion(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": RESEARCHER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,  # Low temp for consistent reasoning
                max_tokens=300,
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            # Parse JSON response
            cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
            result = json.loads(cleaned)
            
            # Validate schema
            if "answer" not in result or "confidence" not in result:
                raise ValueError("LLM response missing required fields")
            
            # Ensure confidence is in valid range
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            result.setdefault("reasoning", "LLM reasoning not provided")
            
            return result
            
        except Exception as exc:
            logger.warning(f"LLM call failed for question '{question}': {exc}")
            logger.info("Falling back to rule-based answer")
            
            # Fallback to rule-based if LLM fails
            return self._formulate_answer_fallback(q_spec, context)
    
    def _build_context_description(
        self, 
        context: dict[str, Any],
        relevant_keys: list[str]
    ) -> str:
        """Build a natural language description of available context."""
        desc_parts = []
        
        if "item_sk" in relevant_keys:
            desc_parts.append(f"- Item SK: {context.get('item_sk', 'Unknown')}")
        
        if "price" in relevant_keys or "price" in context:
            desc_parts.append(f"- Item Price: ${context.get('price', 0):.2f}")
        
        if "return_qty" in relevant_keys or "return_qty" in context:
            desc_parts.append(f"- Return Quantity: {context.get('return_qty', 1)} unit(s)")
        
        if "packaging_condition" in relevant_keys:
            pkg = context.get('packaging_condition', 'Unknown')
            desc_parts.append(f"- Packaging Condition: {pkg}")
        
        if "packaging_factor" in relevant_keys:
            factor = context.get('packaging_factor', 0)
            desc_parts.append(f"- Packaging Damage Factor: {factor:.2f} ({int(factor * 100)}% net loss)")
        
        # Add all context for completeness
        desc_parts.append("\n## Full Context Available:")
        for key, value in context.items():
            desc_parts.append(f"- {key}: {value}")
        
        return "\n".join(desc_parts)
    
    def _formulate_answer_fallback(
        self, 
        q_spec: dict, 
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Fallback rule-based logic when LLM fails.
        Same as original implementation.
        """
        q_key = q_spec["key"]
        
        # Question 1: Seller type
        if q_key == "seller_type":
            return {
                "answer": "Sold & Shipped by Walmart",
                "confidence": 0.7,
                "reasoning": "Default assumption for Item SK in TPC-DS schema"
            }
        
        # Question 2: Purchase/delivery date
        elif q_key == "purchase_date":
            return {
                "answer": "Unknown - requires customer input or order lookup",
                "confidence": 0.3,
                "reasoning": "Purchase date not provided in item context"
            }
        
        # Question 3: Item category
        elif q_key == "item_category":
            return {
                "answer": f"Item SK {context['item_sk']} - category pending lookup",
                "confidence": 0.5,
                "reasoning": "Item category requires Snowflake ITEM table lookup"
            }
        
        # Question 4: Proof of purchase
        elif q_key == "proof_of_purchase":
            pkg = context.get("packaging_condition", "")
            if pkg in ["sealed", "intact"]:
                return {
                    "answer": "Likely available - packaging suggests recent purchase with intact materials",
                    "confidence": 0.6,
                    "reasoning": f"Packaging condition '{pkg}' suggests proof may be intact"
                }
            else:
                return {
                    "answer": "May not be available - damaged packaging suggests proof may be lost",
                    "confidence": 0.4,
                    "reasoning": f"Packaging condition '{pkg}' suggests proof may be compromised"
                }
        
        # Question 5: Return reason
        elif q_key == "return_reason":
            pkg = context.get("packaging_condition", "")
            factor = context.get("packaging_factor", 0)
            
            if pkg in ["destroyed", "heavy"]:
                return {
                    "answer": "Packaging damage during shipping - item potentially unusable",
                    "confidence": 0.8,
                    "reasoning": f"High packaging factor ({factor}) indicates severe damage"
                }
            elif pkg in ["moderate", "minor"]:
                return {
                    "answer": "Packaging shows damage - customer may be concerned about product integrity",
                    "confidence": 0.7,
                    "reasoning": f"Moderate packaging factor ({factor}) suggests concern"
                }
            else:
                return {
                    "answer": "Unknown - undamaged packaging suggests other reason (fit, preference, etc.)",
                    "confidence": 0.5,
                    "reasoning": "No damage signal from packaging assessment"
                }
        
        # Fallback
        return {
            "answer": "Unknown",
            "confidence": 0.0,
            "reasoning": "No logic implemented for this question"
        }
    
    def _build_policy_query(
        self, 
        q_spec: dict, 
        initial_answer: dict[str, Any]
    ) -> str:
        """
        Convert question + answer into a policy validation query.
        
        This query will be sent to Policy Agent for scrapling-based validation.
        """
        q_key = q_spec["key"]
        answer = initial_answer["answer"]
        
        # Build domain-specific query for policy lookup
        if q_key == "seller_type":
            return "walmart return policy marketplace seller"
        
        elif q_key == "purchase_date":
            return "walmart return policy time limit days"
        
        elif q_key == "item_category":
            return f"walmart return policy category {answer}"
        
        elif q_key == "proof_of_purchase":
            return "walmart return policy receipt required"
        
        elif q_key == "return_reason":
            if "damage" in answer.lower():
                return "walmart return policy damaged item"
            else:
                return "walmart return policy general"
        
        return "walmart return policy"
    
    def _adjust_answer(
        self,
        initial_answer: dict[str, Any],
        validation_result: dict[str, Any]
    ) -> tuple[str, float]:
        """
        Adjust answer based on Policy Agent validation feedback.
        
        If validation passes -> use initial answer
        If validation fails -> adjust based on policy guidance
        """
        if validation_result["valid"]:
            # Policy confirms our answer
            return (
                initial_answer["answer"],
                min(1.0, initial_answer["confidence"] + 0.1)  # Boost confidence
            )
        else:
            # Policy suggests adjustment
            note = validation_result.get("note", "")
            if note:
                adjusted = f"{initial_answer['answer']} (Policy note: {note})"
                return (adjusted, initial_answer["confidence"] * 0.8)  # Lower confidence
            else:
                return (initial_answer["answer"], initial_answer["confidence"] * 0.9)
