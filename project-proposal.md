# So You Want to Fix Customer Service With AI. How Hard Could It Be?
---
_(Spoiler: Very. But also — this is actually solvable.)_

Okay, start from the top. What's the actual problem here?

You've sent an angry email to a company before, right? Something broke, or arrived late, or they charged you twice. You typed out this whole detailed message explaining everything — the damaged box, the billing error, the five years you've been a loyal customer — and what came back was a cheerful bot reply about your return request.

Just the return request. Nothing else.

That's not a fluke. That's a structural failure baked into how most customer support systems work. And it costs companies — conservatively — billions of dollars a year in churn, policy errors, and wasted human labor.

--- 

![Header_Image](/agentic-customersupportflow/static/images/proposal_headline.png "Hero Image")

**Okay but isn't this just... a chatbot problem? Don't companies already have those?**

They do. And that's exactly the problem.

Most "AI customer service" today is one of two things: a dumb decision tree that routes you to the wrong FAQ, or someone copying your message into ChatGPT and hoping for the best. Both approaches share the same fundamental flaw — they treat a customer message as *one thing to respond to*, when in reality it's often *five things tangled together*.

Here's a real example. A customer writes:

> *"My order arrived damaged AND it was late AND you charged me twice AND I want to return it. I've been a customer for 5 years and this is unacceptable."*

Count the issues. Go ahead, I'll wait.

There are **five**: damaged item, late delivery, billing error, return request, and — buried in that last sentence — a loyalty signal that says *this person is one bad interaction away from leaving forever*.

A human agent might catch two or three. A chatbot catches one. ChatGPT, if you paste this in cold, will write a polished response that probably addresses the return and sounds reassuring but quietly ignores the double charge.

*Issue dropout*. That's what the industry calls it. And customers notice.

---

**So what does SupportFlow actually do differently?**

This is where it gets interesting.

SupportFlow doesn't try to answer the customer message. It first tries to *understand* the customer message — completely — before a single word of response gets drafted. It does this by splitting the job across four specialized AI agents, each responsible for one concern.

Think of it like a hospital emergency room, not a single overworked doctor.

When you walk into an ER, you don't immediately see the surgeon. First, triage. Then routing. Then treatment. Then a quality check before discharge. Each step handled by someone trained for exactly that step.

SupportFlow works the same way:

```
Customer Message
      │
      ▼
┌─────────────┐
│   TRIAGE    │  → "What are ALL the issues? How angry are they? How urgent?"
└─────────────┘
      │
      ▼
┌─────────────┐
│   ROUTING   │  → "Who handles this? How fast? Does a human need to see this?"
└─────────────┘
      │
      ▼
┌─────────────┐
│   RESPONSE  │  → "What does company policy actually say? Draft the reply."
└─────────────┘
      │
      ▼
┌─────────────┐
│  SUPERVISOR │  → "Did we address EVERYTHING? Is this compliant? Send or escalate?"
└─────────────┘
```

![Robots_Image](/agentic-customersupportflow/static/images/robots_talking.png "Robots Image")

**Wait — four AI agents? Are they like, talking to each other?**

Yes, and that's exactly what makes this architecture interesting rather than just "a really long prompt."

---

**Okay but here's my objection. Can't I just write a really good prompt that says "address ALL issues"?**

You can try! And it'll work... sometimes.

The problem is consistency at scale. A mid-size e-commerce company handles 10,000 to 50,000 support contacts *per month*. During Black Friday? That number triples.

"Address all issues" in a prompt is an instruction. The Supervisor Agent checking a structured list is a *verification mechanism*. One relies on the model following directions. The other actually counts.

There's a useful way to think about this mathematically. If a single prompt handles all five issues correctly 90% of the time — which is optimistic — then across 30,000 messages a month, that's 3,000 customers getting incomplete responses. Every. Single. Month.

Multi-agent verification doesn't eliminate error, but it catches failures *before* they reach the customer instead of after.

---


## Phase 1: The Problem & The "Why" (Importance)

### What specific human pain point does this solve?

E-commerce customer service faces a **scale vs. quality crisis**:

**The Scale Problem:**
- Average e-commerce company receives **10,000-50,000 support contacts monthly**
- Peak periods (Black Friday, Prime Day) see **3-5x normal volume**
- Hiring temporary staff leads to inconsistent quality
- Response time expectations: Chat (<1 min), Email (<4 hours), Social (<1 hour)

**The Quality Problem:**
- **67% of customers** cite bad service experiences as reason for churn
- **33% of customers** will leave after just ONE bad experience
- Human agents are inconsistent: same issue gets different resolutions
- Policy knowledge is tribal—new agents make costly mistakes

**The Complexity Problem:**
A single customer message often contains **multiple intertwined issues**:

> *"My order #12345 arrived damaged AND it was late AND you charged me twice AND I want to return it. I've been a customer for 5 years and this is unacceptable."*

This message contains:
1. Damaged item complaint
2. Shipping delay complaint  
3. Billing error report
4. Return request
5. Loyalty/churn signal
6. Emotional frustration

A human agent might address issue #1 and miss the billing error. A simple chatbot routes to "returns" and ignores the rest. **SupportFlow extracts and tracks ALL issues.**

### How does this solve a problem that isn't already handled by a simple prompt?

**The Gemini/ChatGPT Prompt Approach:**

A support agent could paste the customer message into ChatGPT and ask for a draft response. The result would be polite and generally helpful.

**Why this fails in production:**

| Limitation | Real-World Consequence |
|------------|----------------------|
| **No customer context** | ChatGPT doesn't know this is a $10K lifetime value customer or a first-time buyer. Treatment should differ. |
| **No policy knowledge** | ChatGPT doesn't know your return window is 30 days, or that you can offer max 20% discount without manager approval |
| **No routing logic** | ChatGPT can't decide: Should this go to billing, returns, or a manager? |
| **No escalation triggers** | ChatGPT doesn't flag "I'll dispute with my bank" as a legal/churn risk requiring human review |
| **Inconsistent** | Same scenario prompted twice may get different compensation offers |
| **No quality gates** | No check whether response actually addresses all issues |
| **No urgency detection** | "My wedding is tomorrow and the dress didn't arrive" gets same priority as routine inquiry |

**What SupportFlow adds:**

```
CUSTOMER MESSAGE → 
  
  TRIAGE AGENT:
    - Intent: Return request + Complaint (damaged) + Billing inquiry
    - Sentiment: Frustrated (0.85)
    - Urgency: High (loyalty threat detected)
    - Entities: Order #12345, 5-year customer tenure

  ROUTING AGENT:
    - Primary: Returns Department
    - Secondary: Billing (flag for review)
    - Priority: HIGH (VIP + frustrated + multi-issue)
    - Escalation: Manager notification (churn risk)

  RESPONSE AGENT (with RAG):
    - Retrieved policies: 30-day return window ✓, Damaged item = free return label
    - Compensation authority: Can offer 15% off next order without approval
    - Tone: High empathy (frustration detected)
    - Draft: [Addresses all 5 issues, apologizes, provides concrete resolution path]

  SUPERVISOR AGENT:
    - Issue coverage check: ✓ All 5 issues addressed
    - Policy compliance: ✓ Compensation within limits
    - Tone appropriateness: ✓ Empathetic for frustrated customer
    - Escalation decision: Flag for human/manager review (VIP + churn signal)
    - Confidence: 0.87 → OK for agent review before sending
```

This is a **business process**, not just text generation.

### If this project didn't exist, what would be the cost?

| Cost Category | Industry Benchmark |
|---------------|-------------------|
| **Cost per contact** | $5-12 for human handling vs. $0.50-1 for AI-assisted |
| **Customer churn from bad service** | 67% cite poor service; 10% churn = significant LTV loss |
| **Policy errors** | Wrong refunds/credits cost avg. $15-50 per error |
| **Training new agents** | $1,500-3,000 per agent for 2-week ramp |
| **Response time SLA misses** | $10-50 per breach in B2B contracts |

**Conservative estimate**: For a mid-size e-commerce company (20K contacts/month), intelligent triage + routing + response drafting could save **$50,000-100,000 annually** in labor costs while improving customer satisfaction scores.

---

## Phase 2: Uniqueness & Differentiation (The "Special Sauce")

### The Gemini Test

**Challenge**: "If I can get a similar result by typing a clever prompt into Gemini, why does your system need to exist?"

**My answer has three parts:**

#### 1. Multi-Issue Extraction and Tracking

Single prompts handle one issue at a time. Real customer messages contain multiple issues.

**Example test case:**

> *"Order #55123 wrong size, also you keep emailing me promotions even though I unsubscribed, and where's my loyalty reward points from last month?"*

| Approach | Result |
|----------|--------|
| **Gemini prompt** | Addresses size issue, might mention one other thing |
| **SupportFlow** | Extracts 3 distinct issues, tracks each to resolution, ensures response addresses ALL |

The Triage Agent outputs:
```json
{
  "issues": [
    {"type": "product_issue", "subtype": "wrong_size", "entity": "Order #55123"},
    {"type": "account_issue", "subtype": "email_preferences", "action": "unsubscribe"},
    {"type": "account_issue", "subtype": "loyalty_points", "timeframe": "last_month"}
  ],
  "sentiment": "frustrated",
  "urgency": "medium"
}
```

The Supervisor Agent verifies ALL three issues appear in the final response.

#### 2. Policy-Grounded Responses via RAG

**The problem with generic LLMs**: They make up policies or give generic advice.

> Gemini might say: "We'd be happy to offer you a full refund..."

But your actual policy might be: "Exchanges only for size issues; refunds require manager approval."

**SupportFlow's RAG pipeline:**

```
RESPONSE AGENT queries knowledge base:
  
  Query: "wrong size exchange policy"
  Retrieved: "Size exchanges: Customer may exchange for different size within 
             30 days. Original item must be unworn with tags. Free return 
             shipping label provided. No restocking fee."
  
  Query: "email unsubscribe process"  
  Retrieved: "Email preferences: Customers can unsubscribe via account settings
             or by replying STOP. Processing takes 24-48 hours. Transactional
             emails (order confirmations) cannot be disabled."

  Query: "loyalty points inquiry resolution"
  Retrieved: "Missing points: Check 72-hour posting delay. If >72 hours,
             escalate to loyalty team with order number. Can manually credit
             as goodwill if under 500 points."
```

**The response is grounded in actual company policy, not hallucinated.**

#### 3. Intelligent Routing with Business Context

A prompt can't decide where a ticket should go. SupportFlow routes based on:

| Factor | Routing Impact |
|--------|----------------|
| Issue type | Billing issues → Billing queue |
| Customer lifetime value | High LTV → Priority queue |
| Sentiment × urgency | Frustrated + urgent → Senior agent |
| Churn signals | "Cancel my account" → Retention specialist |
| Legal triggers | "I'll dispute with my bank" → Compliance flag |
| Complexity | Multi-issue → Experienced agent |

**This is business logic that generic LLMs don't have.**

### What "judgmental skill" does this system implement?

**The judgmental skill is: Contextual Prioritization and Policy Application**

When a frustrated VIP customer has a $10 problem, the right answer isn't just "follow the refund policy." It's:
- Recognize the customer value (context)
- Detect the frustration level (sentiment)
- Apply policy flexibly within authority limits (policy)
- Decide whether to exceed limits and escalate (judgment)
- Calibrate tone to repair relationship (empathy)

This requires **coordinated reasoning across multiple concerns**—exactly what multi-agent architecture provides.

### What makes this special?

| Component | Innovation |
|-----------|------------|
| **Multi-issue pipeline** | Extracts, tracks, and verifies resolution of ALL issues in a message |
| **Policy RAG** | Responses grounded in actual company policies, not generic advice |
| **Value-aware routing** | Customer lifetime value influences priority and handling |
| **Sentiment-calibrated responses** | Tone adapts to detected frustration/satisfaction |
| **Quality gates** | Supervisor agent catches incomplete responses before they go out |
| **Escalation intelligence** | Knows when AI should step back and human should take over |

---

## Phase 3: Pre-Technical Evaluation (Measuring Success)

### Ground Truth: What does a perfect output look like?

**A "perfect" SupportFlow response includes:**

| Component | Requirement | Verification Method |
|-----------|-------------|-------------------|
| **Issue coverage** | Addresses 100% of issues extracted from input | Automated checklist |
| **Factual accuracy** | No policy contradictions (e.g., wrong return window) | RAG source verification |
| **Appropriate routing** | Correct department + priority level for issue type | Ground truth labels |
| **Tone calibration** | Empathy level matches detected sentiment | Human rubric |
| **Actionable resolution** | Customer knows exactly what to do next | Clarity rubric |
| **Policy compliance** | Offers within authorization limits | Automated policy check |
| **Proper escalation** | High-risk situations flagged for human review | Trigger verification |

### Silent Failure Definition

**A "Silent Failure" is an output that appears professional and helpful but contains a critical flaw that would cause business harm or customer frustration.**

#### Silent Failure Types I Will Test For:

| Failure Type | Example | Business Impact |
|--------------|---------|-----------------|
| **Issue dropout** | Message has 3 issues; response addresses only 2 | Customer has to contact again; frustration increases |
| **Policy hallucination** | "We offer 90-day returns" (actual: 30 days) | Company loses money or customer is misled |
| **Sentiment mismatch** | Chirpy response to furious customer | Customer feels dismissed; churn risk increases |
| **Misrouting** | Billing issue sent to returns queue | Delay in resolution; wasted labor |
| **Under-escalation** | Legal threat not flagged | Company exposed to dispute/lawsuit |
| **Over-escalation** | Simple question flagged for manager | Manager time wasted; customer wait increases |
| **False confidence** | High confidence on ambiguous case | Agent trusts AI when they shouldn't |
| **Context fabrication** | "Based on your purchase history..." (no history available) | Customer notices BS; trust destroyed |

### Trap Scenario Test Suite

I will create scenarios specifically designed to trigger silent failures:

#### Trap 1: Hidden Issue Dropout
**Input:** 
> "Order #123 arrived late, ALSO the box was damaged, and I need to update my shipping address for future orders."

**Trap:** Three issues that seem like one. Easy to miss address update request.

**Expected:** Response must address: (1) late arrival apology, (2) damage assessment/resolution, (3) address update instructions.

**Silent failure:** Addresses shipping complaint, ignores address update.

---

#### Trap 2: Sarcasm/Sentiment Mismatch
**Input:**
> "Oh GREAT, another late delivery. You guys are really crushing it. 👏"

**Trap:** Positive words, negative sentiment. Emoji adds ambiguity.

**Expected:** Triage Agent detects sarcasm, marks sentiment as frustrated (not positive).

**Silent failure:** Responds cheerfully to perceived compliment.

---

#### Trap 3: Policy Boundary Test  
**Input:**
> "I bought this 35 days ago and want to return it. My friend returned something after 60 days no problem."

**Trap:** Customer is outside return window (if 30-day policy) and cites false precedent.

**Expected:** Response explains actual policy (30 days), offers alternatives (exchange, store credit), does NOT honor the false precedent.

**Silent failure:** Accepts return outside window based on customer's claim, OR rigidly refuses without alternatives.

---

#### Trap 4: VIP + Minor Issue = Priority Test
**Input:**
> Customer with $15K lifetime value asks: "What's the status of my order?"

**Trap:** Simple question from high-value customer.

**Expected:** Routing Agent assigns elevated priority (faster response), even though issue is simple. Response should be personalized.

**Silent failure:** Treats VIP same as first-time buyer; generic bot response.

---

#### Trap 5: Escalation Trigger Detection
**Input:**
> "If you don't fix this I'm going to post about it on Twitter and file a chargeback with my credit card company."

**Trap:** Dual escalation triggers (social media threat + chargeback threat).

**Expected:** Flags for human review, compliance notification.

**Silent failure:** Standard response without escalation flags.

---

#### Trap 6: Multi-Channel Consistency
**Input:** Same issue submitted via chat AND email (duplicate detection test).

**Expected:** System recognizes duplicate, routes to same handler, doesn't send conflicting responses.

**Silent failure:** Two different agents give two different answers.

---

### Evaluation Metrics

| Metric | Type | Target | Measurement |
|--------|------|--------|-------------|
| **Intent Classification Accuracy** | Automated | >90% | Compare to labeled dataset |
| **Sentiment Detection Accuracy** | Automated | >85% | Compare to labeled dataset |
| **Issue Extraction Recall** | Automated | >95% | All issues captured vs. annotated ground truth |
| **Routing Accuracy** | Automated | >90% | Correct department assignment |
| **Policy Faithfulness** | Automated | 100% | Response claims match RAG sources |
| **Trap Scenario Pass Rate** | Automated + Human | >85% | Correct handling of adversarial cases |
| **Response Quality (Human)** | Human rubric | >4.0/5.0 | Clarity, empathy, actionability |
| **Escalation Precision** | Automated | >80% | Correct escalation triggers |
| **Escalation Recall** | Automated | >95% | Don't miss high-risk situations |

### Catching Silent Failures: Automated Checks

```python
def evaluate_response(scenario, triage_output, routing_output, response_output, supervisor_output):
    """Automated evaluation for silent failures"""
    failures = []
    
    # Issue Coverage Check
    extracted_issues = triage_output['issues']
    addressed_issues = supervisor_output['issues_addressed']
    if len(addressed_issues) < len(extracted_issues):
        failures.append(f"ISSUE_DROPOUT: {len(extracted_issues)} extracted, only {len(addressed_issues)} addressed")
    
    # Sentiment-Tone Alignment
    if triage_output['sentiment'] == 'frustrated' and response_output['tone'] == 'cheerful':
        failures.append("SENTIMENT_MISMATCH: Frustrated customer got cheerful response")
    
    # Policy Verification
    for claim in response_output['policy_claims']:
        if not verify_against_rag(claim, response_output['rag_sources']):
            failures.append(f"POLICY_HALLUCINATION: Claim '{claim}' not in sources")
    
    # Escalation Trigger Check
    for trigger in ['chargeback', 'lawyer', 'lawsuit', 'bbb', 'twitter', 'attorney']:
        if trigger in scenario['text'].lower() and not supervisor_output['escalation_flag']:
            failures.append(f"MISSED_ESCALATION: '{trigger}' mentioned but not flagged")
    
    # VIP Priority Check
    if scenario['customer_ltv'] > 5000 and routing_output['priority'] == 'standard':
        failures.append("VIP_DEPRIORITIZED: High-value customer got standard priority")
    
    return failures
```

---

## Phase 4: Data & Knowledge Ethics

### The Source of Truth: Where is my data coming from?

#### Primary Data: Public Datasets

| Dataset | Source | Size | Use | License |
|---------|--------|------|-----|---------|
| **Bitext Customer Support** | HuggingFace | 27K | Intent classification training/eval | Open |
| **Amazon Reviews (subset)** | Public dataset | 10K sampled | Sentiment + complaint detection | Research use |
| **Twitter Customer Support** | Kaggle | 100K+ | Multi-turn conversation patterns | Open |
| **Banking77** | HuggingFace | 13K | Out-of-scope intent detection | Open |

**Advantages of real data:**
- Actual customer language patterns (abbreviations, typos, emotions)
- Real distribution of issue types
- Genuine edge cases I wouldn't think to synthesize

#### Secondary Data: Synthetic Scenarios

For trap scenarios and edge cases not covered in public data, I will create synthetic examples:

| Category | Count | Purpose |
|----------|-------|---------|
| Multi-issue messages | 30 | Test issue extraction |
| Sarcasm/ambiguous sentiment | 20 | Test sentiment detection |
| Policy boundary cases | 20 | Test RAG accuracy |
| VIP scenarios | 15 | Test value-aware routing |
| Escalation triggers | 15 | Test risk detection |
| **Total synthetic** | **100** | Edge case coverage |

#### Tertiary Data: Company Knowledge Base (Simulated)

I will create a **simulated e-commerce company policy database** for RAG:

```markdown
# Simulated Knowledge Base Structure

## Return Policy
- 30-day return window from delivery date
- Items must be unused with original tags
- Exceptions: Final sale items, personalized items
- Damaged items: Full refund + free return shipping

## Compensation Guidelines
- Tier 1 (Agent authority): Up to 15% discount, $25 credit
- Tier 2 (Supervisor required): Up to 30% discount, $75 credit
- Tier 3 (Manager required): Full refund + credit

## Escalation Triggers
- Legal language: "lawyer", "lawsuit", "attorney"
- Financial threats: "chargeback", "dispute", "BBB"
- Social media threats: "twitter", "facebook", "review"
- VIP customers (>$5K LTV) with any complaint

## Customer Tiers
- Standard: <$500 LTV
- Gold: $500-$2,000 LTV  
- Platinum: $2,000-$5,000 LTV
- VIP: >$5,000 LTV
```

**This simulates what a real company would have**, allowing me to test policy grounding.

### How will I handle privacy?

**Public datasets**: All datasets used are either:
- Publicly released for research purposes
- Anonymized (no real customer identifiers)
- Synthetic (created by me)

**No PII in my system:**
- Customer names in scenarios are fictional
- Order numbers are randomly generated
- No real email addresses or phone numbers

**If extended to production:**
- Would require data anonymization pipeline
- PII would be masked before LLM processing
- Retention policies would limit data storage
- Customer consent required for AI processing

### Intellectual Honesty: Source Attribution

SupportFlow's responses include transparent sourcing:

```
RESPONSE AGENT OUTPUT:
{
  "draft_response": "I apologize for the damaged item. Per our policy, you're 
                     entitled to a full refund with free return shipping...",
  "rag_sources": [
    {"doc": "return_policy.md", "section": "Damaged items", "confidence": 0.94},
    {"doc": "compensation_guidelines.md", "section": "Tier 1", "confidence": 0.87}
  ],
  "policy_claims": [
    {"claim": "full refund for damaged items", "source": "return_policy.md#damaged"},
    {"claim": "free return shipping", "source": "return_policy.md#damaged"}
  ]
}
```

**Every policy claim is traceable to a source document.**

### Bias Considerations

| Potential Bias | Mitigation |
|----------------|------------|
| **Sentiment model bias** | Test across demographic groups; use multiple sentiment signals |
| **VIP prioritization** | Ensure base service level is acceptable; VIP is "better" not "basic vs. nothing" |
| **Language/dialect** | Include non-standard English in test cases; test with ESL patterns |
| **Escalation bias** | Audit escalation patterns for demographic skew |

---

## Phase 5: Constraints & Realism

### Minimum Viable Logic (MVL)

**What I am committing to build:**

| Component | Description | Complexity |
|-----------|-------------|------------|
| **Triage Agent** | Intent classification + sentiment analysis + entity extraction | Medium |
| **Routing Agent** | Department assignment + priority scoring + escalation flags | Medium |
| **Response Agent** | RAG-powered response drafting with tone calibration | High |
| **Supervisor Agent** | Quality verification + issue coverage check + final assembly | Medium |
| **RAG Knowledge Base** | Simulated e-commerce policies (15-20 documents) | Low |
| **Evaluation Harness** | Automated testing + trap scenarios + metrics calculation | Medium |
| **Streamlit UI** | Demo interface showing full pipeline | Low |

**What I am explicitly NOT building:**

| Excluded | Reason |
|----------|--------|
| Real-time voice transcription | Out of scope; will use pre-transcribed text |
| Integration with actual ticketing system | Demo only; no Zendesk/Freshdesk integration |
| Production deployment | Proof-of-concept, not production-ready |
| Customer-facing bot | Agent-assist tool, not autonomous customer bot |
| Multi-language support | English only for MVP |

### System Architecture (MVP)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUPPORTFLOW MVP ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  INPUT LAYER                                             │   │
│  │  • Sample conversations (from public datasets)           │   │
│  │  • Synthetic scenarios (trap cases)                      │   │
│  │  • Manual input (Streamlit text box)                     │   │
│  └──────────────────────┬──────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  LANGGRAPH MULTI-AGENT PIPELINE                         │   │
│  │                                                          │   │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐       │   │
│  │  │  TRIAGE    │ → │  ROUTING   │ → │  RESPONSE  │       │   │
│  │  │  AGENT     │   │  AGENT     │   │  AGENT     │       │   │
│  │  └────────────┘   └────────────┘   └─────┬──────┘       │   │
│  │                                          │              │   │
│  │                         ┌────────────────┘              │   │
│  │                         ▼                               │   │
│  │                   ┌────────────┐                        │   │
│  │                   │ SUPERVISOR │                        │   │
│  │                   │   AGENT    │                        │   │
│  │                   └────────────┘                        │   │
│  └──────────────────────┬──────────────────────────────────┘   │
│                         │                                        │
│  ┌──────────────────────┴──────────────────────────────────┐   │
│  │  RAG KNOWLEDGE BASE (ChromaDB / FAISS)                  │   │
│  │  • Return policies    • Compensation limits              │   │
│  │  • Escalation rules   • Product FAQs                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  OUTPUT                                                  │   │
│  │  • Triage results (intent, sentiment, entities)         │   │
│  │  • Routing decision (department, priority, flags)       │   │
│  │  • Draft response (with RAG citations)                  │   │
│  │  • Quality report (coverage, compliance, confidence)    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Timeline (6-Week Project)

| Week | Deliverables | Risk |
|------|--------------|------|
| **Week 1** | Data preparation: download datasets, create synthetic scenarios, build knowledge base | Low |
| **Week 2** | Triage Agent: intent classification, sentiment analysis, entity extraction | Medium |
| **Week 3** | Routing Agent: department logic, priority scoring, escalation rules | Medium |
| **Week 4** | Response Agent: RAG setup, response generation, tone calibration | High |
| **Week 5** | Supervisor Agent + evaluation harness + trap scenario testing | Medium |
| **Week 6** | Streamlit UI, final evaluation, documentation | Low |

### Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Intent classification underperforms** | Medium | High | Use ensemble approach; fall back to broader categories |
| **RAG retrieves wrong policy** | Medium | High | Test retrieval accuracy separately; tune chunk size |
| **Agents disagree problematically** | Low | Medium | Supervisor has final authority; log disagreements for analysis |
| **Evaluation doesn't catch real failures** | Medium | High | Human evaluation component; diverse trap scenarios |
| **Scope creep** | High | Medium | Strict MVP boundaries; "nice to have" list for future work |

### Cost Estimate

| Resource | Usage | Cost |
|----------|-------|------|
| **Claude API (Haiku - development)** | ~800K tokens | ~$0.80 |
| **Claude API (Sonnet - evaluation)** | ~300K tokens | ~$4.50 |
| **Embedding API** | ~100K tokens | ~$0.10 |
| **Buffer (2x)** | Iteration | ~$10.00 |
| **Compute** | Local | $0 |
| **Total** | | **~$15-20** |

### Data Access Confirmation

| Data Need | Status | Source |
|-----------|--------|--------|
| Intent classification data | ✅ Available | Bitext (HuggingFace) |
| Sentiment data | ✅ Available | Amazon Reviews |
| Multi-turn conversations | ✅ Available | Twitter Support Corpus |
| Company policies (RAG) | ✅ Self-created | Simulated KB |
| Trap scenarios | ✅ Self-created | Synthetic |

---

## Phase 6: Portfolio Readiness

### Why This Project Demonstrates Production-Level Thinking

| Criterion | Evidence in This Proposal |
|-----------|--------------------------|
| **Real business problem** | Customer service is universal; quantifiable ROI |
| **Beyond prompt engineering** | Multi-agent pipeline with specialized roles, not single-model |
| **Rigorous evaluation** | Trap scenarios, automated checks, human rubrics |
| **Data ethics** | Public datasets, privacy consideration, bias awareness |
| **Scope discipline** | Clear MVP vs. future work; realistic 6-week plan |
| **Production patterns** | RAG for grounding, escalation logic, quality gates |

### Computational Skepticism Demonstrated

I have explicitly identified:

| Risk Area | Acknowledgment |
|-----------|----------------|
| **Where LLMs fail** | Issue dropout, policy hallucination, sentiment mismatch |
| **How I catch failures** | Automated checks, trap scenarios, human evaluation |
| **What I'm NOT claiming** | Not production-ready, not autonomous (agent-assist only) |
| **Honest limitations** | Simulated policies; real deployment needs actual company data |

### Demo-Ready Artifacts

By project end:

1. **Working Streamlit application** with full pipeline visualization
2. **Evaluation report** with metrics on 200+ test cases
3. **Trap scenario analysis** showing failure detection
4. **LangGraph pipeline code** (documented, reproducible)
5. **3-minute demo video** for portfolio

### Industry Relevance

This project directly applies to:
- **Customer service platforms** (Zendesk, Freshdesk, Intercom)
- **E-commerce companies** (internal support tools)
- **BPO/outsourcing** (agent assist tools)
- **Enterprise AI** (document-grounded response generation)

The skills demonstrated (multi-agent orchestration, RAG, evaluation design) are highly sought after in the current AI job market.

---

## Substack & Building in Public (Optional)

**Consent**: Yes, I give permission for this project to be featured publicly.

**Why I Care**:

Every e-commerce customer has experienced the frustration of explaining an issue three times to three different agents, getting conflicting answers, or having part of their problem ignored. I've been that customer.

What excites me about SupportFlow isn't the technology—it's the possibility of making support interactions actually *helpful*. The multi-agent approach isn't just architecturally interesting; it mirrors how good support teams actually work: a triage person, a routing decision, a specialist who knows the policies, and a quality check before sending.

I want to prove that AI can do more than generate plausible-sounding text—it can orchestrate processes that genuinely solve problems. If SupportFlow works, it's a template for a whole category of "intelligent business process" applications beyond customer service.

---

## Appendix A: Sample Agent Prompts

### Triage Agent System Prompt

```
You are a customer service triage specialist for an e-commerce company. 
Your job is to analyze incoming customer messages and extract:

1. INTENT(S): Classify each distinct issue. Categories:
   - order_status: Tracking, delivery questions
   - return_request: Wants to return/exchange
   - refund_request: Wants money back
   - complaint_product: Item quality, wrong item, damaged
   - complaint_shipping: Late, lost, wrong address
   - complaint_billing: Overcharge, double charge, wrong charge
   - account_issue: Login, password, preferences
   - product_question: Pre-purchase inquiry
   - cancellation: Wants to cancel order
   - feedback: Praise or general feedback
   - other: Doesn't fit categories

2. SENTIMENT: Rate customer emotional state
   - frustrated: Angry, upset, threatening
   - concerned: Worried but calm
   - neutral: Matter-of-fact
   - positive: Happy, complimentary

3. URGENCY: Rate time-sensitivity (1-5)
   - 5: Immediate (legal threat, time-sensitive event)
   - 4: High (VIP customer, multiple issues)
   - 3: Medium (standard complaint)
   - 2: Low (general inquiry)
   - 1: Minimal (feedback, non-urgent question)

4. ENTITIES: Extract specific details
   - Order numbers, product names, dates, amounts, names

CRITICAL: Customers often have MULTIPLE issues in one message. 
Extract ALL distinct issues, not just the first one.

Output valid JSON only.
```

### Routing Agent System Prompt

```
You are a customer service routing specialist. Given triage results and 
customer context, decide:

1. PRIMARY DEPARTMENT:
   - self_service: Simple status checks, FAQ answers
   - returns: Return/exchange processing
   - billing: Payment issues, refunds
   - shipping: Delivery problems, address changes
   - product_specialist: Technical questions, recommendations
   - retention: Cancellation requests, churn risk
   - general_support: Everything else

2. PRIORITY LEVEL:
   - critical: Legal threats, VIP with complaint, social media threat
   - high: VIP customer, multiple issues, high urgency
   - medium: Standard complaint, regular customer
   - low: Simple inquiry, first contact

3. ESCALATION FLAGS:
   - manager_review: Complex case, high compensation likely
   - compliance_alert: Legal/chargeback threats
   - retention_risk: Churn signals detected
   - quality_sample: Random sample for QA

4. HANDLING INSTRUCTIONS:
   - Specific guidance for the agent handling this case

Consider customer lifetime value in priority decisions.
A VIP customer's simple question is higher priority than a new customer's simple question.

Output valid JSON only.
```

---

## Appendix B: Evaluation Scenario Examples

### Scenario 1: Multi-Issue Standard
**Input:**
> "Hi, my order #98765 arrived yesterday but one item was missing (the blue scarf), and I'd also like to know if you have the same scarf in red?"

**Expected Triage:**
- Issues: [missing_item (order #98765, blue scarf), product_question (red scarf availability)]
- Sentiment: neutral
- Urgency: 3

**Expected Routing:**
- Department: general_support (handles both)
- Priority: medium
- Flags: none

---

### Scenario 2: VIP Escalation Test
**Input:**
> "This is the third time my order has been wrong. I spend over $500 a month with you guys and this is how I'm treated?"

**Customer Context:** LTV = $8,500 (VIP tier)

**Expected Triage:**
- Issues: [complaint_product (recurring issue)]
- Sentiment: frustrated
- Urgency: 4 (VIP + pattern complaint)

**Expected Routing:**
- Department: retention (or general_support with retention flag)
- Priority: critical
- Flags: [retention_risk, manager_review]

---

### Scenario 3: Sarcasm Trap
**Input:**
> "Wow, only took 3 weeks for my 'express' shipping. Really impressive service! 🙄"

**Expected Triage:**
- Sentiment: frustrated (NOT positive despite "impressive")
- Issues: [complaint_shipping (late delivery)]
- Urgency: 3

**Expected Response:** Empathetic, acknowledges delay, offers resolution—NOT cheerful response.

---

## References

1. Bitext. (2023). Customer Support Dataset. HuggingFace Datasets.
2. Amazon Customer Reviews Dataset. (2018). UCSD/Stanford.
3. Twitter Customer Support Corpus. (2017). Kaggle.
4. LangGraph Documentation. (2025). Multi-Agent Patterns.
5. RAG Best Practices. (2024). Anthropic Cookbook.

---

*Proposal submitted for SpringBigData Generative AI Final Project, February 2026*
**Author:** Abhinav Gangurde  
**Date:** February 2026