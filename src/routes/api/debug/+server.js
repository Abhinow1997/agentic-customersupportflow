// src/routes/api/debug/+server.js
// Temporary diagnostic endpoint — remove before production
import { json } from '@sveltejs/kit';
import { query } from '$lib/snowflake.js';

export async function GET() {
  const results = {};

  // 1. Raw row count — no joins, no filters
  try {
    const r = await query(`SELECT COUNT(*) AS CNT FROM STORE_RETURNS`);
    results.store_returns_count = r[0]?.CNT ?? r[0]?.cnt ?? 'unknown';
  } catch (e) { results.store_returns_count = `ERROR: ${e.message}`; }

  // 2. Check the columns that actually exist on STORE_RETURNS
  try {
    const r = await query(`
      SELECT COLUMN_NAME, DATA_TYPE
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = 'COMPANY'
        AND TABLE_NAME   = 'STORE_RETURNS'
      ORDER BY ORDINAL_POSITION
    `);
    results.store_returns_columns = r.map(row =>
      `${row.COLUMN_NAME ?? row.column_name} (${row.DATA_TYPE ?? row.data_type})`
    );
  } catch (e) { results.store_returns_columns = `ERROR: ${e.message}`; }

  // 3. Sample one raw row with no joins
  try {
    const r = await query(`SELECT * FROM STORE_RETURNS LIMIT 1`);
    results.sample_raw_row = r[0] ?? 'no rows';
  } catch (e) { results.sample_raw_row = `ERROR: ${e.message}`; }

  // 4. Check JOIN tables exist and have rows
  for (const tbl of ['REASON', 'ITEM', 'CUSTOMER', 'DATE_DIM']) {
    try {
      const r = await query(`SELECT COUNT(*) AS CNT FROM ${tbl}`);
      results[`${tbl.toLowerCase()}_count`] = r[0]?.CNT ?? r[0]?.cnt;
    } catch (e) { results[`${tbl.toLowerCase()}_count`] = `ERROR: ${e.message}`; }
  }

  // 5. Try the full JOIN with no WHERE filters — count only
  try {
    const r = await query(`
      SELECT COUNT(*) AS CNT
      FROM STORE_RETURNS sr
        JOIN REASON   r ON r.R_REASON_SK   = sr.SR_REASON_SK
        JOIN ITEM     i ON i.I_ITEM_SK     = sr.SR_ITEM_SK
        JOIN CUSTOMER c ON c.C_CUSTOMER_SK = sr.SR_CUSTOMER_SK
        JOIN DATE_DIM d ON d.D_DATE_SK     = sr.SR_RETURNED_DATE_SK
    `);
    results.full_join_count_no_filter = r[0]?.CNT ?? r[0]?.cnt;
  } catch (e) { results.full_join_count_no_filter = `ERROR: ${e.message}`; }

  // 6a. Sample PKs from each dimension table
  for (const [tbl, pk] of [['REASON','R_REASON_SK'],['CUSTOMER','C_CUSTOMER_SK'],['DATE_DIM','D_DATE_SK'],['ITEM','I_ITEM_SK']]) {
    try {
      const r = await query(`SELECT ${pk} FROM ${tbl} LIMIT 5`);
      results[`${tbl.toLowerCase()}_sample_pks`] = r.map(row => row[pk] ?? row[pk.toLowerCase()]);
    } catch (e) { results[`${tbl.toLowerCase()}_sample_pks`] = `ERROR: ${e.message}`; }
  }

  // 6. Try with the WHERE filters applied
  try {
    const r = await query(`
      SELECT COUNT(*) AS CNT
      FROM STORE_RETURNS sr
        JOIN REASON   r ON r.R_REASON_SK   = sr.SR_REASON_SK
        JOIN ITEM     i ON i.I_ITEM_SK     = sr.SR_ITEM_SK
        JOIN CUSTOMER c ON c.C_CUSTOMER_SK = sr.SR_CUSTOMER_SK
        JOIN DATE_DIM d ON d.D_DATE_SK     = sr.SR_RETURNED_DATE_SK
      WHERE sr.SR_REASON_SK IS NOT NULL
        AND sr.SR_CUSTOMER_SK IS NOT NULL
        AND sr.SR_RETURNED_DATE_SK IS NOT NULL
        AND sr.SR_ITEM_SK IS NOT NULL
    `);
    results.full_join_count_with_filter = r[0]?.CNT ?? r[0]?.cnt;
  } catch (e) { results.full_join_count_with_filter = `ERROR: ${e.message}`; }

  return json(results, { status: 200 });
}
