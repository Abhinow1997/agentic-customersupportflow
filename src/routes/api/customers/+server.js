// src/routes/api/customers/+server.js
import { json, error } from '@sveltejs/kit';
import { query } from '$lib/snowflake.js';

/**
 * GET /api/customers?email=...
 * Looks up an existing customer by email address.
 * Returns customer details if found, or { found: false } if not.
 */
export async function GET({ url }) {
  const email = url.searchParams.get('email')?.trim();

  if (!email) {
    throw error(400, 'email query parameter is required');
  }

  try {
    const rows = await query(`
      SELECT
        C_CUSTOMER_SK,
        C_FIRST_NAME,
        C_LAST_NAME,
        C_EMAIL_ADDRESS,
        C_PREFERRED_CUST_FLAG
      FROM CUSTOMER
      WHERE LOWER(C_EMAIL_ADDRESS) = LOWER('${email.replace(/'/g, "''")}')
      LIMIT 1
    `);

    if (rows.length === 0) {
      return json({ found: false });
    }

    const row = rows[0];
    const preferred = row.C_PREFERRED_CUST_FLAG === 'Y';

    // Derive tier from preferred flag
    const tier = preferred ? 'Silver' : 'Bronze';

    return json({
      found: true,
      customer: {
        sk:        row.C_CUSTOMER_SK,
        firstName: row.C_FIRST_NAME  ?? '',
        lastName:  row.C_LAST_NAME   ?? '',
        name:      `${row.C_FIRST_NAME ?? ''} ${row.C_LAST_NAME ?? ''}`.trim(),
        email:     row.C_EMAIL_ADDRESS,
        preferred,
        tier,
      }
    });

  } catch (err) {
    console.error('[/api/customers] ERROR:', err.message);
    throw error(500, `Customer lookup failed: ${err.message}`);
  }
}
