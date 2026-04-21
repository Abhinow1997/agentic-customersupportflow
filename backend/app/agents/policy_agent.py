# app/agents/policy_agent.py
import json
import logging
import asyncio
import re
import litellm
from typing import Any
from app.config import get_settings
from app.services.fetch_return_policies import WalmartPolicyFetcher

logger = logging.getLogger("agents.policy")
settings = get_settings()

# System prompt for the Policy Auditor reasoning
POLICY_AUDITOR_PROMPT = """You are a Policy Auditor for Walmart Returns. 
Your task is to validate a "Proposed Answer" against the provided "Policy Source Text".

You must determine:
1. Is the proposed answer factually correct according to the policy?
2. Are there any specific exceptions or windows (e.g., 90 vs 30 days) that conflict?

Important:
- Only judge the exact claim in the proposed answer.
- Do not require unrelated policy details.
- If the policy text does not explicitly support or contradict the answer, return
  compliance_status = "insufficient_evidence" instead of marking it invalid.
- Use "deviation" only when the source text explicitly contradicts the answer.

Respond with ONLY a valid JSON object:
{
  "valid": boolean,
  "compliance_status": "compliant" | "deviation" | "insufficient_evidence" | "error",
  "exact_issue": "The precise mismatch, missing rule, or exception if any.",
  "evidence": "Short quote or paraphrase from the policy that supports the verdict.",
  "note": "A concise explanation of why it is valid or what specifically contradicts it.",
  "confidence": float (0.0 to 1.0)
}
"""

class PolicyAgent:
    """
    Validates Researcher Agent answers against live Walmart return policies
    retrieved via Scrapling.
    """
    
    def __init__(self):
        self.fetcher = WalmartPolicyFetcher()
        self.model = "gpt-4o-mini"
        self._policy_cache: dict[str, dict[str, Any]] = {}
    
    async def validate(
        self,
        question: str,
        proposed_answer: str,
        query: str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Routes the query to the correct Scrapling fetcher and validates the answer.
        """
        logger.info(f"   🛡️ POLICY AGENT: Fetching and Validating")
        
        # 1. ROUTING: Choose the correct fetcher based on the Researcher's query
        cache_key = query.strip().lower()
        policy_data = self._policy_cache.get(cache_key)
        if not policy_data:
            policy_data = await asyncio.to_thread(self._route_and_fetch, query)
            if policy_data:
                self._policy_cache[cache_key] = policy_data
        
        if not policy_data or "Content not found" in policy_data['content']:
            return {
                "valid": False,
                "compliance_status": "error",
                "exact_issue": f"Could not retrieve live policy for query: {query}",
                "evidence": "",
                "note": f"System Error: Could not retrieve live policy for query: {query}",
                "confidence": 0.0,
                "policy_ref": "unknown",
                "source_name": "unknown",
                "retrieved_policies": []
            }

        # 2. AUDITING: Use LLM to compare the Researcher's answer to the live content
        audit_result = await self._audit_with_llm(proposed_answer, policy_data['content'])
        
        return {
            "valid": audit_result["compliance_status"] in ("compliant", "insufficient_evidence"),
            "compliance_status": audit_result.get(
                "compliance_status",
                "compliant" if audit_result.get("valid") else "deviation",
            ),
            "exact_issue": audit_result.get("exact_issue", audit_result.get("note", "")),
            "evidence": audit_result.get("evidence", ""),
            "note": audit_result["note"],
            "confidence": audit_result["confidence"],
            "policy_ref": policy_data["source_url"],
            "source_name": policy_data["policy_title"],
            "retrieved_policies": [policy_data["policy_title"]]
        }

    def _route_and_fetch(self, query: str) -> dict:
        """
        Maps the Researcher's 'policy_query' to a specific Scrapling function.
        """
        q = query.lower()
        
        if "marketplace" in q:
            if "restriction" in q:
                return self.fetcher.get_marketplace_restrictions()
            return self.fetcher.get_marketplace_policy()
        
        if "appliance" in q:
            return self.fetcher.get_major_appliance_policy()
        
        if "refund" in q:
            return self.fetcher.get_refund_timelines()
            
        # Default to standard return policy for all other queries
        return self.fetcher.get_standard_return_policy()

    async def _audit_with_llm(self, proposed_answer: str, policy_text: str) -> dict:
        """
        Uses LiteLLM to cross-reference the proposed answer with the scraped policy text.
        """
        try:
            # Send only the first 4000 characters to manage context windows
            context_snippet = policy_text[:4000]
            
            user_prompt = f"""
            POLICY SOURCE TEXT:
            {context_snippet}

            PROPOSED ANSWER TO VALIDATE:
            {proposed_answer}

            Return the most exact mismatch possible. If the answer is compliant, set
            compliance_status to "compliant" and exact_issue to a short confirmation.
            """

            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": POLICY_AUDITOR_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0, # Deterministic for auditing
                response_format={"type": "json_object"}
            )
            
            parsed = json.loads(response.choices[0].message.content)
            parsed.setdefault("valid", False)
            parsed.setdefault(
                "compliance_status",
                "compliant" if parsed["valid"] else "deviation",
            )
            if parsed.get("compliance_status") == "deviation" and not parsed.get("exact_issue"):
                parsed["compliance_status"] = "insufficient_evidence"
            parsed.setdefault("exact_issue", parsed.get("note", ""))
            parsed.setdefault("evidence", "")
            parsed.setdefault("note", parsed.get("exact_issue", "Policy validation completed."))
            parsed.setdefault("confidence", 0.0)
            return parsed

        except Exception as e:
            logger.error(f"LLM Policy Audit failed: {e}")
            return {
                "valid": False, 
                "compliance_status": "error",
                "exact_issue": "Policy audit failed due to technical error.",
                "evidence": "",
                "note": "Technical failure during policy auditing.", 
                "confidence": 0.0
            }
