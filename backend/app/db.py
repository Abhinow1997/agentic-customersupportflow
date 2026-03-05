# app/db.py
import snowflake.connector
from app.config import get_settings

settings = get_settings()


def get_connection() -> snowflake.connector.SnowflakeConnection:
    """Open and return a fresh Snowflake connection."""
    return snowflake.connector.connect(
        account=settings.SNOWFLAKE_ACCOUNT,
        user=settings.SNOWFLAKE_USERNAME,
        password=settings.SNOWFLAKE_PASSWORD,
        database=settings.SNOWFLAKE_DATABASE,
        schema=settings.SNOWFLAKE_SCHEMA,
        warehouse=settings.SNOWFLAKE_WAREHOUSE,
        role=settings.SNOWFLAKE_ROLE,
    )


def run_query(sql: str, params: tuple = ()) -> list[dict]:
    """
    Execute a SQL query and return rows as a list of dicts.
    Opens a fresh connection per call (suitable for demo scale).
    """
    conn = get_connection()
    try:
        cur = conn.cursor(snowflake.connector.DictCursor)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()
