// src/routes/api/reasons/+server.js
import { json, error } from '@sveltejs/kit';
import { query } from '$lib/snowflake.js';

export async function GET() {
  try {
    const rows = await query(`
      SELECT
        R_REASON_SK,
        R_REASON_ID,
        R_REASON_DESC
      FROM REASON
      ORDER BY R_REASON_SK ASC
    `);

    // Normalize keys to camelCase for the frontend
    const reasons = rows.map(row => ({
      id:   row.R_REASON_SK,
      code: row.R_REASON_ID,
      desc: row.R_REASON_DESC
    }));

    return json({ reasons });

  } catch (err) {
    console.error('[/api/reasons]', err.message);
    throw error(500, `Failed to fetch reasons: ${err.message}`);
  }
}