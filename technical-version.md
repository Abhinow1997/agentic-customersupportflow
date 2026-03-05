# CustomerSupportFlow: Technical Architecture

**Companion doc:** [Conversational explainer](./conversational-explainer.md)  
**System type:** Human-assist support pipeline (not autonomous customer-facing bot)  
**Core claim:** Enforce response *coverage* and *grounding* through multi-agent verification across three distinct service flows.

---

## 1. Design Intent

The system is intentionally built as a truthful demo: not production scale, but structurally sound.

If this architecture performs on representative support data, moving to real company data should primarily be a **configuration and integration change** (knowledge base + connectors + policies), not an end-to-end redesign.

CustomerSupportFlow is organized around **three agentic workflows**, each serving a distinct operational function:

| Flow | Purpose | Primary Input | Output |
|------|---------|---------------|--------|
| **Flow 1: Store Return Processing** | Analyze return requests and recommend resolution decisions using customer/product profile data | Return tickets + Snowflake customer/product data | Resolution recommendation (refund, exchange, escalate) |
| **Flow 2: Ticket Response & Query Resolution** | Draft grounded responses to customer/vendor queries received via email and voicemail | Email tickets, voicemail transcriptions, company rulebook, Snowflake data | Policy-accurate draft response for human review |
| **Flow 3: Proactive Marketing Outreach** | Generate personalized marketing emails based on customer profiles and purchase behavior | Snowflake customer data + purchase/return history | Targeted marketing email drafts |

All three flows share a common data backbone (Snowflake via TPC-DS schema), a RAG layer grounded in company policy documents, and a supervisor verification step before any output reaches a human queue.

---

## 2. Problem Framing

Single-prompt support assistants fail most often through **silent incompleteness**:

- One customer message contains multiple issues.
- The model responds fluently but addresses only a subset.
- Missing issues are rarely obvious at send time.

This is the core failure mode described in the companion article as **issue dropout**.

### Additional Failure Modes Across Flows

**Return processing failures:** Generic return handling that ignores item category, price tier, customer lifetime value, or return reason — leading to blanket refunds where an exchange or retention offer would be more appropriate.

**Query response failures:** Responding to email or voicemail tickets without grounding in the company rulebook or without cross-referencing the customer's actual order/product data from Snowflake, resulting in inaccurate policy claims.

**Marketing failures:** Sending generic promotional emails without leveraging purchase history, return patterns, or customer segmentation — missing opportunities for personalized retention and upsell.

### Example Failure Pattern

Input message may include all of the following in one ticket:

- Damaged item
- Late delivery
- Double charge
- Return request
- Churn/retention signal

A generic response can sound high quality while still missing critical items (often billing or retention risk).

---

## 3. Architecture Overview

CustomerSupportFlow uses a LangGraph-style state machine with specialized agents and explicit handoff contracts. The system branches into three primary flows after an initial intake step.

```text
                    Incoming Request (email / voicemail / return ticket / CRM trigger)
                                          |
                                          v
                                  [INTAKE CLASSIFIER]
                                   Detect flow type
                                /        |         \
                               /         |          \
                              v          v           v
                        FLOW 1       FLOW 2       FLOW 3
                     Store Return   Ticket        Proactive
                     Processing     Response      Marketing
                          |            |              |
                          v            v              v
                     [TRIAGE]    [TRIAGE]       [SEGMENTATION]
                          |            |              |
                          v            v              v
                     [ROUTING]   [ROUTING]      [CAMPAIGN
                          |            |         MATCHING]
                          v            v              |
                     [RESOLUTION  [RESPONSE         v
                      AGENT +      AGENT +     [CONTENT
                       RAG]         RAG]        AGENT +
                          |            |          RAG]
                          v            v           |
                     [SUPERVISOR] [SUPERVISOR]     v
                          |            |      [SUPERVISOR]
                          v            v           |
                     Human Queue  Human Queue      v
                                               Human Queue
```

### Shared State Contract

```python
from typing import TypedDict, List, Dict, Any, Optional

class FlowState(TypedDict):
    flow_type: str                         # "return_processing" | "ticket_response" | "marketing_outreach"
    message: str                           # original input (email body, voicemail transcript, or CRM trigger)
    customer_ctx: Dict[str, Any]           # Snowflake customer profile data

    # Flow 1: Return-specific fields
    return_details: Optional[Dict[str, Any]]   # product info, return reason, quantities, amounts
    resolution: Optional[Dict[str, Any]]       # recommended action (refund/exchange/escalate)

    # Flow 2: Ticket response fields
    triage: Optional[Dict[str, Any]]
    routing: Optional[Dict[str, Any]]
    rag_results: List[Dict[str, Any]]
    response: Optional[Dict[str, Any]]

    # Flow 3: Marketing fields
    segmentation: Optional[Dict[str, Any]]     # customer segment, purchase patterns
    campaign: Optional[Dict[str, Any]]         # matched campaign and content draft

    # Common
    supervisor_report: Dict[str, Any]
```

The state object is the pipeline memory. Each node appends structured output; downstream nodes consume structured fields, not freeform prose.

---

## 4. Flow 1 — Store Return Processing

### 4.1 Purpose

Handle in-store return requests by analyzing the customer's product details, return reason, purchase history, and customer profile (sourced from Snowflake via TPC-DS schema) to recommend the best resolution for the return ticket.

### 4.2 Data Sources (Snowflake / TPC-DS)

The return processing agent pulls from:

- **`store_returns`** — `SR_RETURN_AMT`, `SR_RETURN_QUANTITY`, `SR_REASON_SK`, `SR_ITEM_SK`, `SR_CUSTOMER_SK`
- **`item`** — `I_PRODUCT_NAME`, `I_CATEGORY`, `I_CLASS`, `I_CURRENT_PRICE`
- **`reason`** — `R_REASON_DESC` (e.g., "Did not like the color", "Found a better price")
- **`customer`** / **`customer_demographics`** — lifetime value signals, purchase frequency, demographic segments
- **`store_sales`** (cross-reference) — original transaction details

### 4.3 Triage Agent (Return-Specific)

**Goal:** Extract return details, match product metadata, classify the return reason, and assess customer value.

**Input:** `message`, `customer_ctx`, `return_details` (from Snowflake query)  
**Output:** `triage`

```json
{
  "issues": [
    {"type": "return_request", "subtype": "damaged_item", "entity": "Order #12345", "confidence": 0.95}
  ],
  "item_context": {
    "product_name": "Premium Wireless Headphones",
    "category": "Electronics",
    "class": "portable audio",
    "current_price": 149.99,
    "return_reason": "Product stopped working after 2 weeks",
    "return_quantity": 1,
    "return_amount": 149.99
  },
  "customer_value": {
    "segment": "high_ltv",
    "total_purchases_12m": 12,
    "total_returns_12m": 1,
    "return_rate": 0.08
  },
  "sentiment": "frustrated",
  "urgency": 3,
  "escalation_signals": []
}
```

### 4.4 Resolution Agent

**Goal:** Recommend the optimal return resolution by combining item context, return reason, customer profile, and company policy.

**Decision logic:**

| Return Reason + Category | Recommendation |
|---|---|
| "damaged" + Electronics | Replacement or escalate to quality team |
| "not the right item" + Clothing | Offer size/color exchange first, refund second |
| "no longer needed" + high-value item | Retention offer before processing refund |
| `returnQty > 1` (bulk return) | Flag as bulk buyer, manager review |
| `itemPrice` vs `returnAmt` mismatch | Partial refund evaluation |

**Output:** `resolution`

```json
{
  "recommended_action": "replacement",
  "justification": "Electronics category + defect reason within warranty window. Customer is high-LTV with low return rate.",
  "alternative_action": "full_refund",
  "retention_offer": "15% discount on next electronics purchase",
  "requires_escalation": false,
  "rag_citations": [
    {"claim": "Electronics returns for defects processed as replacements within 30 days", "source_doc": "return_policy.md", "source_section": "4.1", "confidence": 0.94}
  ]
}
```

### 4.5 Pattern Detection (Future Enhancement)

Multiple returns of the same `I_ITEM_SK` across different customers surface a **product quality signal** worth escalating to procurement, not just resolving individually.

---

## 5. Flow 2 — Ticket Response & Query Resolution

### 5.1 Purpose

Respond to customer and vendor queries received via **email tickets** and **voicemail tickets** (transcribed via Whisper). The agent analyzes the query against the company rulebook/policy corpus and customer data from Snowflake, then drafts a grounded response for human review.

### 5.2 Input Channels

**Email tickets:** Parsed directly from the ticketing system. The triage agent extracts all distinct issues from the email body.

**Voicemail tickets:** Audio is transcribed upstream using OpenAI Whisper, then the transcript is fed into the same pipeline as email text. The triage agent accounts for transcription artifacts (filler words, fragmented sentences) during issue extraction.

### 5.3 Triage Agent

**Goal:** Complete issue extraction and risk discovery from email or voicemail transcript.

**Input:** `message`, `customer_ctx`  
**Output:** `triage`

```json
{
  "input_channel": "voicemail",
  "issues": [
    {"type": "complaint_product", "subtype": "damaged_item", "entity": "Order #12345", "confidence": 0.93},
    {"type": "complaint_shipping", "subtype": "late_delivery", "confidence": 0.89},
    {"type": "complaint_billing", "subtype": "double_charge", "confidence": 0.95},
    {"type": "return_request", "confidence": 0.99},
    {"type": "churn_signal", "confidence": 0.84}
  ],
  "sentiment": "frustrated",
  "sentiment_score": -0.82,
  "urgency": 4,
  "escalation_signals": ["chargeback", "attorney", "public_posting"]
}
```

**Key property:** `issues` is treated as a required coverage checklist for downstream validation.

### 5.4 Routing Agent

**Goal:** Decide ownership, SLA priority, and escalation path.

**Input:** `triage`, `customer_ctx`  
**Output:** `routing`

```json
{
  "primary_department": "billing",
  "priority": "high",
  "escalation_flags": {
    "manager_review": true,
    "compliance_alert": false,
    "retention_risk": true
  },
  "handling_instructions": "Address billing correction first, then return workflow, acknowledge loyalty risk.",
  "estimated_resolution_time": "24h"
}
```

### 5.5 Response + RAG Layer

**Goal:** Produce a policy-accurate draft response from retrieved evidence. The RAG layer retrieves from two sources:

1. **Company rulebook / policy corpus** (e.g., return policies, compliance manual, escalation procedures)
2. **Snowflake customer/order data** (order history, product details, account status)

**Input:** `triage`, `routing`, `customer_ctx`, `rag_results`  
**Output:** `response`

```json
{
  "draft_response": "...",
  "tone_applied": "high_empathy",
  "issues_addressed": ["complaint_billing", "return_request", "complaint_shipping", "complaint_product", "churn_signal"],
  "rag_citations": [
    {"claim": "Returns accepted within 30 days", "source_doc": "return_policy.md", "source_section": "3.2", "confidence": 0.91},
    {"claim": "Double charge identified on Order #12345", "source_doc": "snowflake:store_sales", "source_section": "transaction_log", "confidence": 0.97}
  ],
  "requires_escalation": false
}
```

**RAG policy:** If evidence is missing, the agent must defer (for example, "I will confirm that policy") rather than inventing details.

### 5.6 Supervisor Agent

**Goal:** Block silent failures before human review/send.

**Input:** `triage`, `routing`, `response`  
**Output:** `supervisor_report`

```json
{
  "approved": false,
  "recommendation": "revise",
  "failures": [
    {"type": "ISSUE_DROPOUT", "severity": "high", "detail": "Missing: complaint_billing"},
    {"type": "LOW_CONFIDENCE_CLAIM", "severity": "medium", "detail": "Refund eligibility statement"}
  ],
  "confidence_score": 0.71
}
```

---

## 6. Flow 3 — Proactive Marketing Outreach

### 6.1 Purpose

Act as an agentic marketing tool for the company. Using customer profiles, purchase history, and return behavior from Snowflake, the system generates personalized marketing emails targeting retention, upsell, and re-engagement opportunities.

### 6.2 Data Sources (Snowflake / TPC-DS)

- **`customer`** — demographics, preferred address, first purchase date
- **`customer_demographics`** — income bracket, education, household composition
- **`store_sales`** / **`web_sales`** / **`catalog_sales`** — purchase frequency, recency, monetary value (RFM signals)
- **`store_returns`** / **`web_returns`** — return patterns, dissatisfaction signals
- **`item`** — product categories, classes, brands for recommendation matching
- **`promotion`** — active promotions eligible for the customer segment

### 6.3 Segmentation Agent

**Goal:** Classify the customer into an actionable marketing segment based on their Snowflake profile.

**Output:** `segmentation`

```json
{
  "customer_id": "C_12345",
  "segment": "at_risk_high_value",
  "rfm_scores": {"recency": 2, "frequency": 4, "monetary": 5},
  "purchase_categories": ["Electronics", "Home & Garden"],
  "recent_return": true,
  "last_purchase_days_ago": 67,
  "recommended_campaign_type": "retention_winback"
}
```

### 6.4 Campaign Matching Agent

**Goal:** Match the customer segment to an appropriate campaign template and personalization parameters.

**Output:** `campaign`

```json
{
  "campaign_type": "retention_winback",
  "offer": "20% off next Electronics purchase",
  "personalization": {
    "product_recommendations": ["Wireless Earbuds Pro", "Smart Home Hub"],
    "tone": "appreciative",
    "mention_loyalty": true
  },
  "compliance_checks": {
    "opt_in_verified": true,
    "frequency_cap_ok": true,
    "region_restrictions": "none"
  }
}
```

### 6.5 Content Agent + RAG

**Goal:** Draft a personalized marketing email grounded in actual customer data and compliant with company brand guidelines.

**RAG sources:** Brand voice guidelines, promotion terms and conditions, product catalog descriptions.

**Output:** Draft email with subject line, body, and CTA — sent to human marketing queue for review before dispatch.

### 6.6 Supervisor Agent (Marketing)

**Checks:**

- Personalization accuracy (does the email reference correct customer data?)
- Compliance (opt-in, frequency cap, regional restrictions)
- Brand voice alignment
- Offer validity (is the promotion still active and the customer eligible?)

---

## 7. Verification Logic (Core Mechanism)

This is the central architectural difference from a single-prompt system. The verification function applies to all three flows with flow-specific checks.

```python
def verify(flow_type: str, triage: dict, routing: dict, response: dict) -> dict:
    failures = []

    # Common: Issue coverage check (Flow 1 & 2)
    if flow_type in ("return_processing", "ticket_response"):
        expected = {x["type"] for x in triage.get("issues", [])}
        addressed = set(response.get("issues_addressed", []))
        missed = expected - addressed
        if missed:
            failures.append({"type": "ISSUE_DROPOUT", "severity": "high", "detail": sorted(missed)})

    # Common: Citation confidence check (all flows)
    for c in response.get("rag_citations", []):
        if c.get("confidence", 0.0) < 0.70:
            failures.append({"type": "LOW_CONFIDENCE_CLAIM", "severity": "medium", "detail": c.get("claim", "")})

    # Flow 2: Escalation check
    if flow_type == "ticket_response":
        if triage.get("escalation_signals") and not routing.get("escalation_flags", {}).get("compliance_alert"):
            failures.append({"type": "MISSED_ESCALATION", "severity": "critical"})

    # Flow 3: Marketing compliance check
    if flow_type == "marketing_outreach":
        compliance = response.get("compliance_checks", {})
        if not compliance.get("opt_in_verified"):
            failures.append({"type": "MISSING_OPT_IN", "severity": "critical"})
        if not compliance.get("frequency_cap_ok"):
            failures.append({"type": "FREQUENCY_CAP_EXCEEDED", "severity": "high"})

    return {
        "approved": not any(f["severity"] == "critical" for f in failures),
        "recommendation": "send" if not failures else "revise",
        "failures": failures
    }
```

The supervisor enforces *checkable completeness* rather than relying on prompt obedience.

---

## 8. Orchestration Pattern

```python
# Intake classification
flow_type = intake_classifier(incoming_request)

if flow_type == "return_processing":
    # Flow 1
    triage -> routing -> rag_retrieval(snowflake + policy) -> resolution_agent -> supervisor
    
elif flow_type == "ticket_response":
    # Flow 2 (email or voicemail-transcribed)
    whisper_transcribe(if voicemail) -> triage -> routing -> rag_retrieval(rulebook + snowflake) -> response_agent -> supervisor

elif flow_type == "marketing_outreach":
    # Flow 3
    segmentation(snowflake) -> campaign_matching -> content_agent(rag: brand + promo) -> supervisor

# Common decision edge (all flows)
if supervisor.recommendation == "send":
    handoff_to_human_queue()
elif supervisor.recommendation == "revise":
    run_agent_once_more_with_failure_context()
else:
    escalate_to_senior_human_queue()
```

One bounded revision loop is intentional: it captures easy self-corrections without creating unstable retry chains.

---

## 9. Human Accountability Model

This system is **human-assist by design** across all three flows:

- AI never auto-sends customer communications or marketing emails.
- **Flow 1:** Human agents receive return resolution recommendation + product/customer context + policy citations. They approve, modify, or override the recommendation.
- **Flow 2:** Human agents receive draft response + issue checklist + policy citations + risk flags.
- **Flow 3:** Marketing team receives personalized email draft + segmentation rationale + compliance status. They approve before dispatch.
- Escalation-trigger tickets can bypass drafting and route directly to senior review.

This preserves accountability while offloading extraction, synthesis, and policy lookups.

---

## 10. Evaluation Strategy

### Core Metrics (All Flows)

- Issue extraction recall (`triage.issues` completeness)
- Coverage pass rate (`issues_addressed` vs extracted issues)
- Citation faithfulness (claim-to-source confidence)
- Supervisor catch rate on seeded failure cases

### Flow-Specific Metrics

**Flow 1 (Returns):**
- Resolution accuracy (did the recommendation match what a human agent would choose?)
- Customer value utilization (did the agent factor in LTV and return history?)
- Category-aware routing (Electronics vs. Apparel differentiation)

**Flow 2 (Ticket Response):**
- Escalation recall (risk signal detection)
- Voicemail transcription quality impact (does Whisper output degrade triage accuracy?)
- Policy grounding rate (percentage of claims backed by rulebook citation)

**Flow 3 (Marketing):**
- Personalization accuracy (correct product references, segment match)
- Compliance pass rate (opt-in, frequency cap, regional restrictions)
- Campaign-segment alignment

### Adversarial Test Set (examples)

- Multi-issue tickets with conflicting intents
- Sarcastic sentiment masking urgency
- Policy edge cases near eligibility boundaries
- High-LTV customers with minor surface issue but high churn signals
- Dual escalation triggers in one message
- Voicemail transcripts with heavy filler words and fragmented sentences
- Return tickets where `itemPrice` vs `returnAmt` mismatch suggests partial return
- Marketing targeting for recently churned customers (sensitivity check)

### Silent Failure Definition

A response that appears polished but fails any of:

- Missed extracted issue
- Unsupported policy claim
- Missed required escalation
- Misaligned tone for detected sentiment severity
- Return resolution that ignores customer value signals
- Marketing email referencing incorrect product or expired promotion

---

## 11. Scope and Limitations (Explicit)

- Uses representative/simulated policy corpus in demo mode.
- Customer and product data sourced from Snowflake TPC-DS sample dataset (representative schema, not production customer data).
- Voicemail transcription assumes upstream Whisper integration; text input is the direct interface.
- English-first behavior unless multilingual components are added.
- Mocked customer context can be replaced by CRM connectors.
- Marketing flow assumes opt-in/consent data is available in the customer profile.

These are integration constraints, not architecture blockers.

---

## Source Data Point References

1. [Bitext. (2023). Customer Support Dataset. HuggingFace Datasets.](https://huggingface.co/datasets/bitext/Bitext-retail-ecommerce-llm-chatbot-training-dataset)
2. [Sample Customer data: TPC-DS](https://docs.snowflake.com/en/user-guide/sample-data-tpcds#database-entities-relationships-and-characteristics)
3. [TPC-DS: Schema Definition](https://www.tpc.org/TPC_Documents_Current_Versions/pdf/TPC-DS_v2.5.0.pdf)
4. [OpenAI Whisper](https://github.com/openai/whisper)
5. [Walmart's US Product Quality and Compliance Manual](https://corporate.walmart.com/content/dam/corporate/documents/suppliers/requirements/compliance-areas/u-s-product-quality-and-compliance-manual.pdf)
---
