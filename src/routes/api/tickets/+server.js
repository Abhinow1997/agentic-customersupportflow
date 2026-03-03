// src/routes/api/tickets/+server.js
import { json, error } from '@sveltejs/kit';
import { query } from '$lib/snowflake.js';

export async function GET({ url }) {
  try {
    const limit  = parseInt(url.searchParams.get('limit')  ?? '50');
    const offset = parseInt(url.searchParams.get('offset') ?? '0');

    const rows = await query(`
      SELECT
        sr.SR_TICKET_NUMBER,
        sr.SR_RETURN_AMT,
        sr.SR_FEE,
        sr.SR_NET_LOSS,
        sr.SR_RETURN_QUANTITY,
        r.R_REASON_SK,
        r.R_REASON_ID,
        r.R_REASON_DESC,
        c.C_CUSTOMER_SK,
        c.C_FIRST_NAME,
        c.C_LAST_NAME,
        c.C_EMAIL_ADDRESS,
        c.C_PREFERRED_CUST_FLAG,
        d.D_DATE
      FROM STORE_RETURNS sr
        JOIN REASON   r ON r.R_REASON_SK   = sr.SR_REASON_SK
        JOIN CUSTOMER c ON c.C_CUSTOMER_SK = sr.SR_CUSTOMER_SK
        JOIN DATE_DIM d ON d.D_DATE_SK     = sr.SR_RETURNED_DATE_SK
      WHERE sr.SR_REASON_SK IS NOT NULL
        AND sr.SR_CUSTOMER_SK IS NOT NULL
        AND sr.SR_RETURNED_DATE_SK IS NOT NULL
      ORDER BY sr.SR_RETURNED_DATE_SK DESC, sr.SR_TICKET_NUMBER
      LIMIT ${limit} OFFSET ${offset}
    `);

    // Debug: log first row's keys so we can see exact column names
    if (rows.length > 0) {
      console.log('[tickets] first row keys:', Object.keys(rows[0]));
      console.log('[tickets] first row sample:', JSON.stringify(rows[0]));
    } else {
      console.log('[tickets] query returned 0 rows');
    }

    const tickets = rows.map((row, idx) => mapRowToTicket(row, idx));
    return json({ tickets, total: tickets.length });

  } catch (err) {
    console.error('[/api/tickets] ERROR:', err.message);
    throw error(500, `Failed to fetch tickets: ${err.message}`);
  }
}

function mapRowToTicket(row, idx) {
  // Use exact Snowflake column names (uppercase, no alias)
  const ticketNum  = row.SR_TICKET_NUMBER;
  const returnAmt  = parseFloat(row.SR_RETURN_AMT  ?? 0);
  const netLoss    = parseFloat(row.SR_NET_LOSS     ?? 0);
  const returnQty  = parseInt(row.SR_RETURN_QUANTITY ?? 1);
  const firstName  = row.C_FIRST_NAME ?? '';
  const lastName   = row.C_LAST_NAME  ?? '';
  const email      = row.C_EMAIL_ADDRESS   ?? 'no-email@unknown.com';
  const preferred  = row.C_PREFERRED_CUST_FLAG === 'Y';
  const reasonDesc = row.R_REASON_DESC ?? 'General inquiry';
  const returnDate = row.D_DATE;

  const id = `TKT-${ticketNum ?? idx + 1}`;

  const priority =
    netLoss > 500 ? 'critical' :
    netLoss > 200 ? 'high'     :
    netLoss > 50  ? 'medium'   : 'low';

  const sentimentScore =
    netLoss > 500 ? -0.85 :
    netLoss > 200 ? -0.65 :
    netLoss > 50  ? -0.40 : -0.15;

  const sentiment =
    sentimentScore <= -0.7 ? 'frustrated' :
    sentimentScore <= -0.4 ? 'dissatisfied' : 'neutral';

  const issueType  = reasonDescToIssueType(reasonDesc);
  const escalation = netLoss > 500 || returnQty > 5 ? ['high_value_return'] : [];

  const tier =
    preferred && returnAmt > 300 ? 'Gold'   :
    preferred                    ? 'Silver' : 'Bronze';

  return {
    id,
    customer: {
      name:   `${firstName} ${lastName}`.trim() || 'Unknown Customer',
      email,
      tier,
      ltv:    `$${(returnAmt * 3.5).toFixed(0)}`,
      orders: Math.max(1, Math.floor(returnAmt / 40))
    },
    subject:   `Return request — ${reasonDesc}`,
    preview:   `Return for order #${ticketNum}. Reason: ${reasonDesc}. Amount: $${returnAmt.toFixed(2)}.`,
    channel:   'email',
    created:   returnDate ? new Date(returnDate).toISOString() : new Date().toISOString(),
    updated:   returnDate ? new Date(returnDate).toISOString() : new Date().toISOString(),
    status:    'open',
    priority,
    sentiment,
    sentiment_score: sentimentScore,
    urgency:   priority === 'critical' ? 5 : priority === 'high' ? 4 : priority === 'medium' ? 2 : 1,
    department: issueType.includes('billing') ? 'billing' : 'fulfillment',
    issues: [
      { type: issueType, subtype: 'return_request', entity: `Order #${ticketNum}`, confidence: 0.95 },
      ...(netLoss > 200 ? [{ type: 'complaint_billing', subtype: 'refund_request', entity: `$${returnAmt.toFixed(2)}`, confidence: 0.88 }] : []),
      ...(returnQty > 3 ? [{ type: 'return_request', confidence: 0.99 }] : []),
      ...(escalation.length ? [{ type: 'churn_signal', confidence: 0.72 }] : [])
    ],
    escalation_signals: escalation,
    ai_draft: null,
    ai_citations: [],
    supervisor: {
      approved:         false,
      recommendation:   'revise',
      confidence_score: 0.6,
      failures: [{ type: 'DRAFT_PENDING', severity: 'medium', detail: 'AI draft not yet generated' }]
    }
  };
}

function reasonDescToIssueType(desc = '') {
  const d = desc.toLowerCase();
  if (d.includes('damaged') || d.includes('broken'))       return 'complaint_product';
  if (d.includes('time')    || d.includes('late'))         return 'complaint_shipping';
  if (d.includes('not the right') || d.includes('wrong'))  return 'complaint_product';
  if (d.includes('no longer needed'))                       return 'return_request';
  if (d.includes('work')   || d.includes('defect'))        return 'complaint_product';
  if (d.includes('price')  || d.includes('charge'))        return 'complaint_billing';
  return 'general_inquiry';
}