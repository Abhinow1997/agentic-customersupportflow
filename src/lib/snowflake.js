// src/lib/snowflake.js
// Server-side only — never imported in client components
import snowflake from 'snowflake-sdk';

import {
  SNOWFLAKE_ACCOUNT,
  SNOWFLAKE_USERNAME,
  SNOWFLAKE_PASSWORD,
  SNOWFLAKE_DATABASE,
  SNOWFLAKE_SCHEMA,
  SNOWFLAKE_WAREHOUSE,
  SNOWFLAKE_ROLE
} from '$env/static/private';

function createConnection() {
  return snowflake.createConnection({
    account:   SNOWFLAKE_ACCOUNT,
    username:  SNOWFLAKE_USERNAME,
    password:  SNOWFLAKE_PASSWORD,
    database:  SNOWFLAKE_DATABASE,
    schema:    SNOWFLAKE_SCHEMA,
    warehouse: SNOWFLAKE_WAREHOUSE,
    role:      SNOWFLAKE_ROLE
  });
}

/**
 * Run a SQL query and return rows as plain objects.
 * Opens a fresh connection per call (fine for demo scale).
 */
export function query(sql, binds = []) {
  return new Promise((resolve, reject) => {
    const conn = createConnection();

    conn.connect((connErr) => {
      if (connErr) {
        reject(new Error(`Snowflake connection failed: ${connErr.message}`));
        return;
      }

      conn.execute({
        sqlText: sql,
        binds,
        complete: (queryErr, _stmt, rows) => {
          conn.destroy(() => {});   // always release connection
          if (queryErr) {
            reject(new Error(`Snowflake query failed: ${queryErr.message}`));
          } else {
            resolve(rows ?? []);
          }
        }
      });
    });
  });
}