// src/lib/data.js
export const MOCK_TICKETS = [
  {
    id: "TKT-0041",
    customer: { name: "Sarah Mitchell", email: "s.mitchell@email.com", tier: "Gold", ltv: "$2,840", orders: 34 },
    subject: "Damaged item + double charge + return request",
    preview: "Hi, my order #12345 arrived completely broken and I was charged twice. I need a refund and I'm considering canceling my account...",
    channel: "email",
    created: "2025-03-02T08:14:00",
    updated: "2025-03-02T08:14:00",
    status: "open",
    priority: "critical",
    sentiment: "frustrated",
    sentiment_score: -0.82,
    urgency: 5,
    department: "billing",
    issues: [
      { type: "complaint_product", subtype: "damaged_item", entity: "Order #12345", confidence: 0.93 },
      { type: "complaint_billing", subtype: "double_charge", entity: "Order #12345", confidence: 0.95 },
      { type: "return_request", confidence: 0.99 },
      { type: "churn_signal", confidence: 0.84 }
    ],
    escalation_signals: ["chargeback", "account_cancel"],
    ai_draft: `Dear Sarah,\n\nThank you for reaching out, and I sincerely apologize for the experience with your recent order.\n\nRegarding the damaged item on Order #12345 — this is not acceptable, and we will send a replacement immediately at no cost to you.\n\nFor the double charge, I can confirm our billing team has flagged this for immediate reversal. You should see the correction reflected within 3–5 business days.\n\nYour return request has been approved. A prepaid return label has been generated and will be sent to your email within the hour.\n\nAs a Gold member, your loyalty means a great deal to us. I'd like to personally offer a $50 store credit as an acknowledgment of the inconvenience caused.\n\nPlease don't hesitate to reach out directly if you need anything further.\n\nWarm regards,\n[Agent Name]\nArcella Customer Care`,
    ai_citations: [
      { claim: "Replacement policy for damaged items", source: "fulfillment_policy.md §4.1", confidence: 0.94 },
      { claim: "Billing reversal timeline 3–5 days", source: "billing_policy.md §2.3", confidence: 0.88 },
      { claim: "$50 retention credit for Gold tier", source: "loyalty_program.md §6.2", confidence: 0.91 }
    ],
    supervisor: { approved: true, recommendation: "send", confidence_score: 0.91, failures: [] }
  },
  {
    id: "TKT-0040",
    customer: { name: "James Okafor", email: "j.okafor@gmail.com", tier: "Silver", ltv: "$890", orders: 12 },
    subject: "Where is my order? Late delivery",
    preview: "It's been 2 weeks since I placed my order and tracking hasn't updated in 5 days. This is unacceptable...",
    channel: "email",
    created: "2025-03-02T07:30:00",
    updated: "2025-03-02T07:30:00",
    status: "pending",
    priority: "high",
    sentiment: "angry",
    sentiment_score: -0.71,
    urgency: 4,
    department: "shipping",
    issues: [
      { type: "complaint_shipping", subtype: "late_delivery", entity: "Order #11987", confidence: 0.97 },
      { type: "complaint_shipping", subtype: "tracking_stalled", entity: "Order #11987", confidence: 0.93 }
    ],
    escalation_signals: [],
    ai_draft: `Dear James,\n\nI completely understand your frustration — a two-week delay with no tracking update is genuinely concerning.\n\nI've investigated your Order #11987 and can see the shipment has been stuck at the Miami sorting facility due to a carrier delay. I've escalated this directly to our fulfillment partner.\n\nYou have two options: I can either continue tracking and expedite delivery with priority shipping, or issue a full refund immediately. Please let me know your preference and I'll act on it right away.\n\nI'm sorry for this experience.\n\n[Agent Name]\nArcella Customer Care`,
    ai_citations: [
      { claim: "Carrier delay escalation process", source: "shipping_policy.md §3.4", confidence: 0.86 },
      { claim: "Full refund for orders >10 days late", source: "fulfillment_policy.md §5.1", confidence: 0.92 }
    ],
    supervisor: { approved: true, recommendation: "send", confidence_score: 0.87, failures: [] }
  },
  {
    id: "TKT-0039",
    customer: { name: "Priya Sharma", email: "priya.s@company.io", tier: "Platinum", ltv: "$12,400", orders: 156 },
    subject: "Wrong size sent + need urgent replacement for event",
    preview: "I ordered size M but received size XL. I need this replaced urgently before Friday for a corporate event...",
    channel: "email",
    created: "2025-03-01T16:45:00",
    updated: "2025-03-01T17:20:00",
    status: "open",
    priority: "high",
    sentiment: "anxious",
    sentiment_score: -0.55,
    urgency: 5,
    department: "fulfillment",
    issues: [
      { type: "complaint_product", subtype: "wrong_item", entity: "Order #11801", confidence: 0.99 },
      { type: "replacement_request", confidence: 0.97 },
      { type: "urgency_flag", subtype: "time_sensitive", confidence: 0.91 }
    ],
    escalation_signals: ["high_ltv", "time_sensitive"],
    ai_draft: null,
    ai_citations: [],
    supervisor: {
      approved: false,
      recommendation: "revise",
      confidence_score: 0.52,
      failures: [
        { type: "ISSUE_DROPOUT", severity: "high", detail: "urgency_flag not addressed" },
        { type: "LOW_CONFIDENCE_CLAIM", severity: "medium", detail: "Express shipping eligibility unverified" }
      ]
    }
  },
  {
    id: "TKT-0038",
    customer: { name: "Tom Bergmann", email: "tbergmann@outlook.com", tier: "Bronze", ltv: "$210", orders: 3 },
    subject: "How do I apply a promo code?",
    preview: "Hi, I have a promo code SAVE20 but it's not working at checkout. Can you help?",
    channel: "email",
    created: "2025-03-01T14:10:00",
    updated: "2025-03-01T14:10:00",
    status: "open",
    priority: "low",
    sentiment: "neutral",
    sentiment_score: 0.1,
    urgency: 1,
    department: "general",
    issues: [
      { type: "inquiry_promo", subtype: "code_not_working", confidence: 0.98 }
    ],
    escalation_signals: [],
    ai_draft: `Hi Tom,\n\nThanks for reaching out!\n\nThe promo code SAVE20 is valid for orders over $50. If your cart total is below that threshold, the code won't apply at checkout. Simply add more items to qualify, or check the promotional terms in your email for any category restrictions.\n\nIf your order does meet the minimum and you're still experiencing issues, please try clearing your browser cache or using a different browser. If the problem persists, reply here and I'll apply the discount manually for you.\n\nHappy shopping!\n\n[Agent Name]\nArcella Customer Care`,
    ai_citations: [
      { claim: "SAVE20 requires $50 minimum order", source: "promotions_db.md §current", confidence: 0.95 }
    ],
    supervisor: { approved: true, recommendation: "send", confidence_score: 0.95, failures: [] }
  },
  {
    id: "TKT-0037",
    customer: { name: "Elena Vasquez", email: "e.vasquez@mail.com", tier: "Gold", ltv: "$3,100", orders: 41 },
    subject: "Billing dispute — unauthorized charge",
    preview: "There's a charge of $189 on my card from Arcella that I did not authorize. I'm filing a chargeback...",
    channel: "email",
    created: "2025-03-01T11:00:00",
    updated: "2025-03-01T11:45:00",
    status: "escalated",
    priority: "critical",
    sentiment: "furious",
    sentiment_score: -0.94,
    urgency: 5,
    department: "billing",
    issues: [
      { type: "complaint_billing", subtype: "unauthorized_charge", confidence: 0.99 },
      { type: "churn_signal", confidence: 0.92 }
    ],
    escalation_signals: ["chargeback", "fraud_claim"],
    ai_draft: null,
    ai_citations: [],
    supervisor: {
      approved: false,
      recommendation: "escalate",
      confidence_score: 0.3,
      failures: [
        { type: "MISSED_ESCALATION", severity: "critical", detail: "Fraud/chargeback requires compliance review" }
      ]
    }
  },
  {
    id: "TKT-0036",
    customer: { name: "Marcus Lee", email: "m.lee88@gmail.com", tier: "Silver", ltv: "$760", orders: 9 },
    subject: "Request to cancel subscription",
    preview: "I want to cancel my Arcella Plus subscription. I haven't been using it and I'm being charged monthly.",
    channel: "email",
    created: "2025-02-28T09:30:00",
    updated: "2025-02-28T09:30:00",
    status: "resolved",
    priority: "medium",
    sentiment: "neutral",
    sentiment_score: -0.2,
    urgency: 2,
    department: "subscriptions",
    issues: [
      { type: "cancellation_request", subtype: "subscription", confidence: 0.99 }
    ],
    escalation_signals: [],
    ai_draft: `Hi Marcus,\n\nI've processed your cancellation request for Arcella Plus. Your subscription will remain active until the end of your current billing period on March 15th, after which you won't be charged again.\n\nIf you change your mind, you can reactivate anytime from your account settings — we'd love to have you back.\n\nIs there anything about the service we could have improved? Your feedback genuinely helps us.\n\nBest,\n[Agent Name]\nArcella Customer Care`,
    ai_citations: [
      { claim: "Subscription active until end of billing period", source: "subscription_policy.md §2.1", confidence: 0.97 }
    ],
    supervisor: { approved: true, recommendation: "send", confidence_score: 0.97, failures: [] }
  }
];

export const AGENTS = [
  { id: "agent-1", name: "Daphne K.", role: "Senior Agent", avatar: "DK" },
  { id: "agent-2", name: "Ravi P.", role: "Support Agent", avatar: "RP" },
  { id: "agent-3", name: "Mei L.", role: "Support Agent", avatar: "ML" }
];

export const CURRENT_AGENT = {
  id: "agent-1",
  name: "Daphne K.",
  role: "Senior Support Agent",
  avatar: "DK",
  email: "daphne.k@arcella.com"
};
