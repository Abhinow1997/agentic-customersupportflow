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
        i.I_ITEM_SK,
        i.I_PRODUCT_NAME,
        i.I_CATEGORY,
        i.I_CLASS,
        i.I_CURRENT_PRICE,
        c.C_CUSTOMER_SK,
        c.C_FIRST_NAME,
        c.C_LAST_NAME,
        c.C_EMAIL_ADDRESS,
        c.C_PREFERRED_CUST_FLAG,
        d.D_DATE,
        COALESCE(sr.SR_STATUS, 'Open')        AS SR_STATUS,
        COALESCE(sr.SR_RESOLUTION, '')          AS SR_RESOLUTION,
        COALESCE(rc.RETURN_COUNT, 0)            AS CUSTOMER_ORDER_COUNT
      FROM STORE_RETURNS sr
        JOIN REASON   r ON r.R_REASON_SK   = sr.SR_REASON_SK
        JOIN ITEM     i ON i.I_ITEM_SK     = sr.SR_ITEM_SK
        JOIN CUSTOMER c ON c.C_CUSTOMER_SK = sr.SR_CUSTOMER_SK
        JOIN DATE_DIM d ON d.D_DATE_SK     = sr.SR_RETURNED_DATE_SK
        LEFT JOIN (
          SELECT SR_CUSTOMER_SK,
                 COUNT(DISTINCT SR_TICKET_NUMBER) AS RETURN_COUNT
          FROM STORE_RETURNS
          WHERE SR_CUSTOMER_SK IS NOT NULL
          GROUP BY SR_CUSTOMER_SK
        ) rc ON rc.SR_CUSTOMER_SK = sr.SR_CUSTOMER_SK
      WHERE sr.SR_REASON_SK IS NOT NULL
        AND sr.SR_CUSTOMER_SK IS NOT NULL
        AND sr.SR_RETURNED_DATE_SK IS NOT NULL
        AND sr.SR_ITEM_SK IS NOT NULL
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

    // STORE_RETURNS is a fact table — deduplicate by ticket number, keeping highest net_loss row
    const seen = new Map();
    rows.forEach((row, idx) => {
      const key = row.SR_TICKET_NUMBER ?? idx;
      const existing = seen.get(key);
      const netLoss = parseFloat(row.SR_NET_LOSS ?? 0);
      if (!existing || netLoss > parseFloat(existing.SR_NET_LOSS ?? 0)) {
        seen.set(key, row);
      }
    });
    const uniqueRows = Array.from(seen.values());
    const tickets = uniqueRows.map((row, idx) => mapRowToTicket(row, idx));
    return json({ tickets, total: tickets.length });

  } catch (err) {
    console.error('[/api/tickets] ERROR:', err.message);
    throw error(500, `Failed to fetch tickets: ${err.message}`);
  }
}

function mapRowToTicket(row, idx) {
  // Use exact Snowflake column names (uppercase, no alias)
  const ticketNum   = row.SR_TICKET_NUMBER;
  const returnAmt   = parseFloat(row.SR_RETURN_AMT    ?? 0);
  const netLoss     = parseFloat(row.SR_NET_LOSS       ?? 0);
  const returnQty   = parseInt(row.SR_RETURN_QUANTITY  ?? 1);
  const firstName   = row.C_FIRST_NAME  ?? '';
  const lastName    = row.C_LAST_NAME   ?? '';
  const email       = row.C_EMAIL_ADDRESS ?? 'no-email@unknown.com';
  const preferred   = row.C_PREFERRED_CUST_FLAG === 'Y';
  const reasonDesc  = row.R_REASON_DESC ?? 'General inquiry';
  const returnDate  = row.D_DATE;
  // Item fields (new)
  const productName = row.I_PRODUCT_NAME  ?? 'Unknown Product';
  const category    = row.I_CATEGORY      ?? 'General';
  const itemClass   = row.I_CLASS         ?? '';
  const itemPrice   = parseFloat(row.I_CURRENT_PRICE ?? 0);

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
  const triage     = buildTriage(reasonDesc, category, itemPrice, returnAmt, returnQty, netLoss, preferred);

  const tier =
    preferred && returnAmt > 300 ? 'Gold'   :
    preferred                    ? 'Silver' : 'Bronze';

  // Apply category-based priority override on top of financial priority
  const finalPriority = triage.priorityOverride ?? (
    netLoss > 500 ? 'critical' :
    netLoss > 200 ? 'high'     :
    netLoss > 50  ? 'medium'   : 'low'
  );

  return {
    id,
    // Flat financial fields — used directly by dashboard
    returnAmt:    returnAmt.toFixed(2),
    netLoss:      netLoss.toFixed(2),
    fee:          parseFloat(row.SR_FEE ?? 0).toFixed(2),
    returnReason: reasonDesc,
    customer: {
      name:   `${firstName} ${lastName}`.trim() || 'Unknown Customer',
      email,
      tier,
      ltv:    `${(returnAmt * 3.5).toFixed(0)}`,
      orders: parseInt(row.CUSTOMER_ORDER_COUNT ?? 0)
    },
    item: {
      name:     productName,
      category,
      class:    itemClass,
      price:    `${itemPrice.toFixed(2)}`,
      returnQty
    },
    subject:   `Return — ${productName} (${reasonDesc})`,
    preview:   `${firstName} is returning ${returnQty}x ${productName} (${category}). Reason: ${reasonDesc}. Return amount: ${returnAmt.toFixed(2)}.`,
    channel:   'email',
    created:   returnDate ? new Date(returnDate).toISOString() : new Date().toISOString(),
    updated:   returnDate ? new Date(returnDate).toISOString() : new Date().toISOString(),
    status:     (row.SR_STATUS && row.SR_STATUS !== '') ? row.SR_STATUS : 'Open',
    resolution: (row.SR_RESOLUTION && row.SR_RESOLUTION !== '') ? row.SR_RESOLUTION : null,
    priority:   finalPriority,
    triage,
    sentiment,
    sentiment_score: sentimentScore,
    urgency:   finalPriority === 'critical' ? 5 : finalPriority === 'high' ? 4 : finalPriority === 'medium' ? 2 : 1,
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

// PATCH /api/tickets  { id, status, resolution? }
export async function PATCH({ request }) {
  try {
    const { id, status, resolution } = await request.json();

    const ticketNumber = id.replace('TKT-', '');

    const allowed = ['Open', 'Closed'];
    if (!allowed.includes(status)) {
      throw error(400, `Invalid status. Must be one of: ${allowed.join(', ')}`);
    }

    // Build SET clause — always update status, optionally resolution
    const setClauses = [`SR_STATUS = '${status}'`];
    if (resolution) setClauses.push(`SR_RESOLUTION = '${resolution}'`);

    // SR_TICKET_NUMBER is VARCHAR in Snowflake — must quote the value
    const sql = `UPDATE STORE_RETURNS SET ${setClauses.join(', ')} WHERE SR_TICKET_NUMBER = '${ticketNumber}'`;
    console.log('[PATCH /api/tickets] Executing:', sql);
    const result = await query(sql);
    console.log('[PATCH /api/tickets] Result:', JSON.stringify(result));

    return json({ ok: true, id, status, resolution: resolution ?? null });
  } catch (err) {
    console.error('[PATCH /api/tickets] ERROR:', err.message);
    throw error(500, `Failed to update ticket: ${err.message}`);
  }
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

// ---------------------------------------------------------------------------
// Triage engine — reason + category + financials → recommendation
// ---------------------------------------------------------------------------
function buildTriage(reasonDesc, category, itemPrice, returnAmt, returnQty, netLoss, preferred) {
  const r = reasonDesc.toLowerCase();
  const c = category.toLowerCase();

  // ── 1. Issue classification ──────────────────────────────────────────────
  const isDamaged       = r.includes('damaged')  || r.includes('broken');
  const isWrongItem     = r.includes('not the right') || r.includes('wrong');
  const isDefective     = r.includes('work')     || r.includes('defect') || r.includes('stopped');
  const isUnwanted      = r.includes('no longer needed') || r.includes('unwanted');
  const isSizeFit       = r.includes('size')     || r.includes('fit')    || r.includes('too small') || r.includes('too large');
  const isLateSlow      = r.includes('time')     || r.includes('late')   || r.includes('slow');

  const isElectronics   = c.includes('electronics') || c.includes('computers') || c.includes('music') || c.includes('jewelry');
  const isApparel       = c.includes('clothing') || c.includes('apparel') || c.includes('women') || c.includes('men') || c.includes('children') || c.includes('shoes') || c.includes('sports');
  const isHighValue     = itemPrice > 200 || returnAmt > 200;
  const isBulkReturn    = returnQty > 1;

  // ── 2. Priority elevation ─────────────────────────────────────────────────
  // Category + reason gives a second signal on top of net loss
  let priorityOverride = null;
  if (isDamaged && isElectronics)           priorityOverride = 'critical'; // damaged electronics always critical
  else if (isDefective && isElectronics)    priorityOverride = 'critical';
  else if (isBulkReturn && returnQty > 5)   priorityOverride = 'high';
  else if (isUnwanted && isHighValue && preferred) priorityOverride = 'high'; // retention risk

  // ── 3. Primary resolution action ─────────────────────────────────────────
  let action, actionLabel, actionRationale;

  if (isDamaged && isElectronics) {
    action        = 'replacement_escalate';
    actionLabel   = 'Replace & Escalate to Quality Team';
    actionRationale = 'Damaged electronics require replacement and a quality team review to flag potential batch defects.';
  } else if (isDamaged) {
    action        = 'replacement';
    actionLabel   = 'Send Replacement';
    actionRationale = 'Item arrived damaged — direct replacement is the fastest resolution.';
  } else if (isDefective) {
    action        = 'replacement';
    actionLabel   = 'Send Replacement';
    actionRationale = `Product stopped working. ${isElectronics ? 'Escalate to quality team after replacing.' : 'Issue replacement immediately.'}`;
  } else if (isWrongItem || isSizeFit) {
    if (isApparel) {
      action        = 'exchange_first';
      actionLabel   = 'Offer Size Exchange First';
      actionRationale = 'Wrong size or fit on apparel — offer an exchange before initiating a refund to preserve the sale.';
    } else {
      action        = 'replacement';
      actionLabel   = 'Send Correct Item';
      actionRationale = 'Wrong item was shipped — send the correct one and arrange return of original.';
    }
  } else if (isUnwanted) {
    if (isHighValue && preferred) {
      action        = 'retention_offer';
      actionLabel   = 'Retention Offer Before Refund';
      actionRationale = `High-value item (${itemPrice.toFixed(0)}) from a preferred customer. Offer a discount or store credit before processing the refund to reduce churn risk.`;
    } else {
      action        = 'refund';
      actionLabel   = 'Process Refund';
      actionRationale = 'Customer no longer needs the item — standard refund.';
    }
  } else if (isLateSlow) {
    action        = 'refund_or_reship';
    actionLabel   = 'Refund or Reship';
    actionRationale = 'Late delivery — offer customer choice of full refund or expedited reship.';
  } else {
    action        = 'refund';
    actionLabel   = 'Process Refund';
    actionRationale = 'Standard return — process refund per policy.';
  }

  // ── 4. Refund vs replacement signal ──────────────────────────────────────
  let refundSignal;
  if (returnAmt < itemPrice * 0.9) {
    refundSignal = { type: 'partial', note: `Return amount (${returnAmt.toFixed(2)}) is less than item price (${itemPrice.toFixed(2)}) — likely a partial return.` };
  } else if (isBulkReturn) {
    refundSignal = { type: 'bulk', note: `${returnQty} units returned — bulk return, verify all units before issuing full refund.` };
  } else {
    refundSignal = { type: 'full', note: 'Full single-unit return — standard full refund.' };
  }

  // ── 5. Policy section reference ───────────────────────────────────────────
  const policyRef = isElectronics
    ? 'Electronics Return Policy §4.2 — 15-day return window, must be unopened or defective'
    : isApparel
    ? 'Apparel Return Policy §3.1 — 30-day return window, tags must be attached'
    : 'General Return Policy §2.1 — 30-day return window';

  // ── 6. Flags ──────────────────────────────────────────────────────────────
  const flags = [];
  if (isDamaged && isElectronics)          flags.push({ type: 'quality_escalation', label: 'Quality Team Alert', severity: 'high' });
  if (isBulkReturn && returnQty > 3)       flags.push({ type: 'bulk_return',        label: `Bulk Return (${returnQty} units)`,   severity: 'medium' });
  if (isUnwanted && isHighValue && preferred) flags.push({ type: 'churn_risk',      label: 'Churn Risk — Preferred Customer',    severity: 'high' });
  if (netLoss > 500)                       flags.push({ type: 'high_loss',          label: `High Net Loss (${netLoss.toFixed(2)})`, severity: 'critical' });

  return {
    action,
    actionLabel,
    actionRationale,
    refundSignal,
    policyRef,
    flags,
    priorityOverride
  };
}