# CustomerSupportFlow: Technical Architecture

**Companion doc:** [Conversational explainer](./conversational-explainer.md)  
**System type:** Human-assist support pipeline (not autonomous customer-facing bot)  
**Core claim:** Enforce response *coverage* and *grounding* through multi-agent verification.

---

## 1. Design Intent

The system is intentionally built as a truthful demo: not production scale, but structurally sound.

If this architecture performs on representative support data, moving to real company data should primarily be a **configuration and integration change** (knowledge base + connectors + policies), not an end-to-end redesign.

---

## 2. Problem Framing

Single-prompt support assistants fail most often through **silent incompleteness**:

- One customer message contains multiple issues.
- The model responds fluently but addresses only a subset.
- Missing issues are rarely obvious at send time.

This is the core failure mode described in the companion article as **issue dropout**.

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

CustomerSupportFlow uses a LangGraph-style state machine with specialized agents and explicit handoff contracts.

```text
Customer Message + Context
        |
        v
[1] TRIAGE       -> extract all issues + sentiment + urgency + risk signals
        |
        v
[2] ROUTING      -> priority, ownership, escalation requirements
        |
        v
[3] RESPONSE+RAG -> retrieve policy evidence, draft grounded response
        |
        v
[4] SUPERVISOR   -> verify coverage + grounding + escalation correctness
        |
        +--> send to human queue (always)
              with recommendation: send / revise / escalate
```

### Shared State Contract

```python
from typing import TypedDict, List, Dict, Any

class FlowState(TypedDict):
    message: str
    customer_ctx: Dict[str, Any]

    triage: Dict[str, Any]
    routing: Dict[str, Any]
    rag_results: List[Dict[str, Any]]
    response: Dict[str, Any]
    supervisor_report: Dict[str, Any]
```

The state object is the pipeline memory. Each node appends structured output; downstream nodes consume structured fields, not freeform prose.

---

## 4. Agent Contracts

## 4.1 Triage Agent

**Goal:** Complete issue extraction and risk discovery.

**Input:** `message`, `customer_ctx`  
**Output:** `triage`

```json
{
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

## 4.2 Routing Agent

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

## 4.3 Response + RAG Layer

**Goal:** Produce policy-accurate draft from retrieved evidence.

**Input:** `triage`, `routing`, `customer_ctx`, `rag_results`  
**Output:** `response`

```json
{
  "draft_response": "...",
  "tone_applied": "high_empathy",
  "issues_addressed": ["complaint_billing", "return_request", "complaint_shipping", "complaint_product", "churn_signal"],
  "rag_citations": [
    {"claim": "Returns accepted within 30 days", "source_doc": "return_policy.md", "source_section": "3.2", "confidence": 0.91}
  ],
  "requires_escalation": false
}
```

**RAG policy:** If evidence is missing, the agent must defer (for example, "I will confirm that policy") rather than inventing details.

## 4.4 Supervisor Agent

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

## 5. Verification Logic (Core Mechanism)

This is the central architectural difference from a single-prompt system.

```python
def verify(triage: dict, routing: dict, response: dict) -> dict:
    failures = []

    expected = {x["type"] for x in triage.get("issues", [])}
    addressed = set(response.get("issues_addressed", []))
    missed = expected - addressed
    if missed:
        failures.append({"type": "ISSUE_DROPOUT", "severity": "high", "detail": sorted(missed)})

    for c in response.get("rag_citations", []):
        if c.get("confidence", 0.0) < 0.70:
            failures.append({"type": "LOW_CONFIDENCE_CLAIM", "severity": "medium", "detail": c.get("claim", "")})

    if triage.get("escalation_signals") and not routing.get("escalation_flags", {}).get("compliance_alert"):
        failures.append({"type": "MISSED_ESCALATION", "severity": "critical"})

    return {
        "approved": not any(f["severity"] == "critical" for f in failures),
        "recommendation": "send" if not failures else "revise",
        "failures": failures
    }
```

The supervisor enforces *checkable completeness* rather than relying on prompt obedience.

---

## 6. Orchestration Pattern

```python
# Simplified graph flow
triage -> routing -> rag_retrieval -> response -> supervisor

# Decision edge
if supervisor.recommendation == "send":
    handoff_to_human_queue()
elif supervisor.recommendation == "revise":
    run_response_once_more_with_failure_context()
else:
    escalate_to_senior_human_queue()
```

One bounded revision loop is intentional: it captures easy self-corrections without creating unstable retry chains.

---

## 7. Human Accountability Model

This system is **human-assist by design**:

- AI never auto-sends customer communications.
- Human agents receive draft + issue checklist + policy citations + risk flags.
- Escalation-trigger tickets can bypass drafting and route directly to senior review.

This preserves accountability while offloading extraction, synthesis, and policy lookups.

---

## 8. Evaluation Strategy

### Core Metrics

- Issue extraction recall (`triage.issues` completeness)
- Coverage pass rate (`issues_addressed` vs extracted issues)
- Escalation recall (risk signal detection)
- Citation faithfulness (claim-to-source confidence)
- Supervisor catch rate on seeded failure cases

### Adversarial Test Set (examples)

- Multi-issue tickets with conflicting intents
- Sarcastic sentiment masking urgency
- Policy edge cases near eligibility boundaries
- High-LTV customers with minor surface issue but high churn signals
- Dual escalation triggers in one message

### Silent Failure Definition

A response that appears polished but fails any of:

- Missed extracted issue
- Unsupported policy claim
- Missed required escalation
- Misaligned tone for detected sentiment severity

---

## 9. Scope and Limitations (Explicit)

- Uses representative/simulated policy corpus in demo mode.
- Assumes text input (voice transcription can be integrated upstream).
- English-first behavior unless multilingual components are added.
- Mocked customer context can be replaced by CRM connectors.

These are integration constraints, not architecture blockers.

