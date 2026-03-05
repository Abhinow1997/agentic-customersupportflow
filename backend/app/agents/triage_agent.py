# app/agents/triage_agent.py
"""
Triage Agent -- LangGraph node powered by LiteLLM + OpenAI.

ALL LLM calls go exclusively through LiteLLM. Provider is a one-line
config change: swap LLM_MODEL. Currently using OpenAI gpt-4o-mini.

Strategy
--------
The LLM receives a structured ticket brief covering THREE lenses:

  1. CUSTOMER PROFILE  -- tier, estimated LTV, prior return count, preferred flag.
     High-value / preferred customers get retention-first recommendations.

  2. ITEM CONTEXT      -- product name, category, class, listed price, qty returned.
     Category drives policy window selection (electronics 15d vs apparel 30d vs general 30d).
     Price vs return amount signals partial vs full return.

  3. RETURN SIGNAL     -- reason description + financial damage (return amt, net loss).
     Drives the primary action choice and flags (bulk, high-loss, quality escalation).

The model must return ONLY a JSON object matching the TriageOutput schema.
If the LLM call fails for any reason, the rule-based fallback runs instead
so the UI never breaks.
"""
from __future__ import annotations
import json
import os
import re

import litellm
from app.agents.state import FlowState
from app.config import get_settings

settings = get_settings()

# LiteLLM model alias -- change this one string to swap providers:
#   OpenAI   : "gpt-4o", "gpt-4o-mini"
#   Anthropic: "claude-3-5-haiku-20241022"
#   Gemini   : "gemini/gemini-1.5-pro"
LLM_MODEL = "gpt-4o-mini"

# System prompt
SYSTEM_PROMPT = """You are a senior customer support triage specialist for Arcella,
an e-commerce company. Your job is to analyze product return tickets and recommend
the optimal resolution action.

You will receive a structured ticket brief and must respond with ONLY a valid JSON
object -- no markdown, no preamble, no explanation outside the JSON.

## Resolution Actions (use exactly these strings for the "action" field)
- refund               : Standard full refund, no issues detected
- refund_or_reship     : Late/lost delivery -- let customer choose
- replacement          : Item damaged, defective, or wrong item sent
- replacement_escalate : Damaged/defective electronics -- replace AND flag quality team
- exchange_first       : Wrong size/fit on apparel -- offer exchange before refund
- retention_offer      : Unwanted high-value item from preferred customer -- offer credit first
- escalate_quality     : Batch defect suspected, multiple units affected

## Customer Tier Guide
- Bronze  : Standard policy, no special treatment
- Silver  : Slight priority, standard compensation
- Gold    : Elevated priority, can offer retention credit up to $50
- Platinum: Highest priority, retention is critical, can offer credit up to $100

## Policy Windows (cite the exact string in policyRef)
- Electronics : "Electronics Return Policy section 4.2 -- 15-day return window, must be unopened or defective"
- Apparel     : "Apparel Return Policy section 3.1 -- 30-day return window, tags must be attached"
- All others  : "General Return Policy section 2.1 -- 30-day return window"

## Required JSON schema
{
  "action": "<action string from list above>",
  "actionLabel": "<short human-readable label, max 6 words>",
  "actionRationale": "<1-2 sentence rationale referencing customer tier and item context>",
  "refundSignal": {
    "type": "full" or "partial" or "bulk",
    "note": "<one sentence explaining the signal>"
  },
  "policyRef": "<exact policy string from guide above>",
  "flags": [
    {
      "type": "<snake_case_type>",
      "label": "<short display label>",
      "severity": "low" or "medium" or "high" or "critical"
    }
  ],
  "priorityOverride": "low" or "medium" or "high" or "critical" or null
}

Rules:
- flags array may be empty []
- priorityOverride is null unless there is a strong reason to elevate
  (damaged electronics, bulk return >5 units, high net loss >$500, churn risk on Gold/Platinum)
- actionRationale MUST reference at least one of: customer tier, item category, or financial impact
- Respond with ONLY the JSON object. No other text whatsoever.
"""


# LangGraph node

def triage_node(state: FlowState) -> FlowState:
    """
    LangGraph node: calls LiteLLM with a structured ticket brief and
    writes the parsed triage result into state["triage"].
    Falls back to rule engine if the LLM call fails.
    """
    try:
        brief  = _build_brief(state)
        raw    = _call_llm(brief)
        triage = _parse_response(raw)
        return {**state, "triage": triage, "error": None}
    except Exception as exc:
        try:
            fallback = _rule_fallback(state)
            return {**state, "triage": fallback, "error": f"LLM failed ({exc}), used rule fallback"}
        except Exception as fallback_exc:
            return {**state, "triage": {}, "error": str(fallback_exc)}


# Brief builder

def _build_brief(state: FlowState) -> str:
    cust = state.get("customer_ctx", {})
    item = state.get("item_ctx", {})

    return_amt = float(state.get("return_amt", 0) or 0)
    net_loss   = float(state.get("net_loss",   0) or 0)
    item_price = float(item.get("price", 0) or 0)
    return_qty = int(item.get("return_qty", 1) or 1)

    partial_signal = return_amt < item_price * 0.9 and item_price > 0
    bulk_signal    = return_qty > 1
    high_loss      = net_loss > 500
    preferred      = cust.get("tier") in ("Gold", "Platinum")

    return f"""## Ticket Brief

### Customer Profile
- Name    : {cust.get('name', 'Unknown')}
- Tier    : {cust.get('tier', 'Bronze')}
- Est. LTV: {cust.get('ltv', 'unknown')}
- Prior returns on record: {cust.get('orders', 0)}
- Preferred customer: {'Yes' if preferred else 'No'}

### Item Context
- Product  : {item.get('name', 'Unknown')}
- Category : {item.get('category', 'General')}
- Class    : {item.get('class', '--')}
- Listed price: ${item_price:.2f}
- Qty returned: {return_qty}

### Return Signal
- Reason description: "{state.get('return_reason', '')}"
- Return amount : ${return_amt:.2f}
- Net loss      : ${net_loss:.2f}

### Derived Signals (pre-computed for your reference)
- Partial return detected : {partial_signal}
- Bulk return (>1 unit)   : {bulk_signal}
- High net loss (>$500)   : {high_loss}
- Preferred / high-tier   : {preferred}

Analyze the above and return the triage JSON."""


# LLM call via LiteLLM (OpenAI)

def _call_llm(brief: str) -> str:
    # LiteLLM reads OPENAI_API_KEY from the environment automatically
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

    response = litellm.completion(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": brief},
        ],
        temperature=0.1,   # low temp for consistent structured output
        max_tokens=800,
    )
    return response.choices[0].message.content.strip()


# JSON parser

def _parse_response(raw: str) -> dict:
    # Strip any accidental markdown fences
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    data    = json.loads(cleaned)

    required = {"action", "actionLabel", "actionRationale", "refundSignal", "policyRef", "flags"}
    missing  = required - data.keys()
    if missing:
        raise ValueError(f"LLM response missing keys: {missing}")

    data.setdefault("priorityOverride", None)
    return data


# Rule-based fallback

def _rule_fallback(state: FlowState) -> dict:
    """Deterministic fallback used when the LLM call fails."""
    cust = state.get("customer_ctx", {})
    item = state.get("item_ctx", {})

    reason_desc = state.get("return_reason", "")
    category    = item.get("category", "")
    item_price  = float(item.get("price", 0) or 0)
    return_amt  = float(state.get("return_amt", 0) or 0)
    return_qty  = int(item.get("return_qty", 1) or 1)
    net_loss    = float(state.get("net_loss", 0) or 0)
    preferred   = cust.get("tier") in ("Gold", "Platinum")

    r = reason_desc.lower()
    c = category.lower()

    is_damaged   = "damaged" in r or "broken" in r
    is_wrong     = "not the right" in r or "wrong" in r
    is_defective = "work" in r or "defect" in r or "stopped" in r
    is_unwanted  = "no longer needed" in r or "unwanted" in r
    is_size      = "size" in r or "fit" in r
    is_late      = "time" in r or "late" in r or "slow" in r
    is_elec      = any(k in c for k in ("electronics", "computers", "music", "jewelry"))
    is_apparel   = any(k in c for k in ("clothing", "apparel", "women", "men", "children", "shoes", "sports"))
    is_high_val  = item_price > 200 or return_amt > 200
    is_bulk      = return_qty > 1

    if is_damaged and is_elec:
        action, label, rationale = "replacement_escalate", "Replace & Escalate to Quality Team", "Damaged electronics require replacement and quality team review."
    elif is_damaged:
        action, label, rationale = "replacement", "Send Replacement", "Item arrived damaged -- direct replacement is fastest."
    elif is_defective:
        action, label, rationale = "replacement", "Send Replacement", "Defective product -- issue replacement immediately."
    elif (is_wrong or is_size) and is_apparel:
        action, label, rationale = "exchange_first", "Offer Size Exchange First", "Wrong size on apparel -- offer exchange before refund."
    elif is_wrong or is_size:
        action, label, rationale = "replacement", "Send Correct Item", "Wrong item shipped -- send correct item."
    elif is_unwanted and is_high_val and preferred:
        action, label, rationale = "retention_offer", "Retention Offer Before Refund", "High-value item from preferred customer -- offer credit before refunding."
    elif is_late:
        action, label, rationale = "refund_or_reship", "Refund or Reship", "Late delivery -- let customer choose."
    else:
        action, label, rationale = "refund", "Process Refund", "Standard return -- process refund per policy."

    if return_amt < item_price * 0.9 and item_price > 0:
        refund_signal = {"type": "partial", "note": f"Return amount (${return_amt:.2f}) < item price (${item_price:.2f})."}
    elif is_bulk:
        refund_signal = {"type": "bulk",    "note": f"{return_qty} units -- verify all before refunding."}
    else:
        refund_signal = {"type": "full",    "note": "Full single-unit return."}

    if is_elec:
        policy_ref = "Electronics Return Policy section 4.2 -- 15-day return window, must be unopened or defective"
    elif is_apparel:
        policy_ref = "Apparel Return Policy section 3.1 -- 30-day return window, tags must be attached"
    else:
        policy_ref = "General Return Policy section 2.1 -- 30-day return window"

    flags: list[dict] = []
    if is_damaged and is_elec:
        flags.append({"type": "quality_escalation", "label": "Quality Team Alert",                "severity": "high"})
    if is_bulk and return_qty > 3:
        flags.append({"type": "bulk_return",        "label": f"Bulk Return ({return_qty} units)", "severity": "medium"})
    if is_unwanted and is_high_val and preferred:
        flags.append({"type": "churn_risk",         "label": "Churn Risk -- Preferred Customer",  "severity": "high"})
    if net_loss > 500:
        flags.append({"type": "high_loss",          "label": f"High Net Loss (${net_loss:.2f})",   "severity": "critical"})

    priority_override = (
        "critical" if (is_damaged or is_defective) and is_elec
        else "high" if is_bulk and return_qty > 5
        else "high" if is_unwanted and is_high_val and preferred
        else None
    )

    return {
        "action": action, "actionLabel": label, "actionRationale": rationale,
        "refundSignal": refund_signal, "policyRef": policy_ref,
        "flags": flags, "priorityOverride": priority_override,
    }
