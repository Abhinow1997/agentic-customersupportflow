# app/agents/response_agent.py
"""
Response Agent -- LangGraph node that drafts a grounded customer response.

Reads:
  - state["triage"]       (action, rationale, flags)
  - state["routing"]      (department, priority, instructions)
  - state["rag_results"]  (policy citations from ChromaDB)
  - state["customer_ctx"] (name, tier, ltv)
  - state["item_ctx"]     (product, category, price)

Writes:
  - state["response"]  { draft_response, tone_applied, issues_addressed,
                          rag_citations, requires_escalation }

Uses LiteLLM (same provider as triage_agent) to generate the draft,
but grounds it in the RAG policy citations.
"""
from __future__ import annotations

import json
import os
import re
import logging

import litellm
from app.agents.state import FlowState
from app.config import get_settings

logger = logging.getLogger("agents.response")
settings = get_settings()

LLM_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a customer support response writer for Arcella,
an e-commerce company. You draft professional, empathetic customer-facing
responses grounded in verified policy citations.

CRITICAL RULES:
1. ONLY cite policies from the "Policy Citations" section provided.
2. If evidence is missing for a claim, write "I will confirm that policy"
   -- NEVER invent policy details.
3. Reference the customer by first name.
4. Address ALL issues identified in the triage.
5. Match tone to customer tier: Bronze=friendly, Silver=attentive,
   Gold=premium, Platinum=white-glove.
6. Keep the response under 200 words.

You must respond with ONLY a valid JSON object:
{
  "draft_response": "<the customer-facing email text>",
  "tone_applied": "standard" or "empathetic" or "premium" or "urgent",
  "issues_addressed": ["<issue1>", "<issue2>"],
  "rag_citations": [
    {
      "claim": "<what you cited>",
      "source_doc": "<policy name>",
      "source_section": "<section>",
      "confidence": <0.0-1.0>
    }
  ],
  "requires_escalation": false
}
"""


def response_node(state: FlowState) -> FlowState:
    """
    LangGraph node: draft a grounded customer response.
    Falls back to a template if the LLM call fails.
    """
    try:
        brief = _build_brief(state)
        raw   = _call_llm(brief)
        resp  = _parse_response(raw)
        return {**state, "response": resp}
    except Exception as exc:
        logger.error("Response agent LLM failed: %s", exc)
        fallback = _template_fallback(state)
        return {**state, "response": fallback, "error": f"Response LLM failed ({exc}), used template"}


def _build_brief(state: FlowState) -> str:
    triage  = state.get("triage", {})
    routing = state.get("routing", {})
    cust    = state.get("customer_ctx", {})
    item    = state.get("item_ctx", {})
    rag     = state.get("rag_results", [])

    # Format RAG citations for the prompt
    citations_text = "No policy citations available."
    if rag:
        lines = []
        for i, r in enumerate(rag, 1):
            lines.append(
                f"  [{i}] {r.get('source_doc', '?')} > {r.get('source_section', '?')} "
                f"(conf: {r.get('confidence', 0):.2f})\n"
                f"      \"{r.get('claim', '')[:200]}\""
            )
        citations_text = "\n".join(lines)

    first_name = (cust.get("name", "Customer").split()[0])

    return f"""## Customer Response Brief

### Customer
- Name: {cust.get('name', 'Customer')} (first name: {first_name})
- Tier: {cust.get('tier', 'Bronze')}
- LTV: {cust.get('ltv', 'unknown')}

### Item
- Product: {item.get('name', 'Unknown')}
- Category: {item.get('category', 'General')}
- Price: ${item.get('price', '0')}

### Triage Decision
- Action: {triage.get('action', 'refund')}
- Label: {triage.get('actionLabel', '')}
- Rationale: {triage.get('actionRationale', '')}

### Routing
- Department: {routing.get('primary_department', 'general')}
- Priority: {routing.get('priority', 'medium')}
- Instructions: {routing.get('handling_instructions', '')}

### Return Context
- Reason: {state.get('return_reason', '')}
- Return Amount: ${state.get('return_amt', 0)}
- Net Loss: ${state.get('net_loss', 0)}

### Policy Citations (from RAG -- ONLY cite from these)
{citations_text}

Draft a customer response addressing all issues. Ground claims in the citations above."""


def _call_llm(brief: str) -> str:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    response = litellm.completion(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": brief},
        ],
        temperature=0.3,
        max_tokens=1000,
    )
    return response.choices[0].message.content.strip()


def _parse_response(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    data = json.loads(cleaned)

    required = {"draft_response", "tone_applied", "issues_addressed", "rag_citations"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Response missing keys: {missing}")

    data.setdefault("requires_escalation", False)
    return data


def _template_fallback(state: FlowState) -> dict:
    """Simple template when LLM is unavailable."""
    cust   = state.get("customer_ctx", {})
    item   = state.get("item_ctx", {})
    triage = state.get("triage", {})
    first  = (cust.get("name", "Customer").split()[0])
    action = triage.get("actionLabel", "process your return")

    draft = (
        f"Dear {first},\n\n"
        f"Thank you for reaching out regarding your {item.get('name', 'item')} return. "
        f"We will {action.lower()} as quickly as possible.\n\n"
        f"If you have any questions, please don't hesitate to reply.\n\n"
        f"Best regards,\n[Agent Name]\nArcella Customer Care"
    )

    return {
        "draft_response": draft,
        "tone_applied": "standard",
        "issues_addressed": [triage.get("action", "refund")],
        "rag_citations": [],
        "requires_escalation": False,
    }
