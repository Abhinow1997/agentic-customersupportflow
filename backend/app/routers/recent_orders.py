from fastapi import APIRouter, HTTPException
import snowflake.connector
import os

# Create a FastAPI router for the recent orders endpoints
router = APIRouter()

def get_snowflake_connection():
    """Establish and return a connection to Snowflake."""
    required_env = ["SNOWFLAKE_USERNAME", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_ACCOUNT"]
    missing = [k for k in required_env if not os.getenv(k)]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"Snowflake not configured (missing env vars: {', '.join(missing)})",
        )
    try:
        return snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USERNAME"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
            database=os.getenv("SNOWFLAKE_DATABASE", "SYNTHETIC_COMPANYDB"),
            schema=os.getenv("SNOWFLAKE_SCHEMA", "COMPANY")
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Snowflake connection failed: {str(e)}")

@router.get("/api/recent_orders")
async def get_recent_orders():
    """
    Fetch the most recent 20 store sales orders alongside customer and item details.
    """
    query = """
    SELECT
        c.C_FIRST_NAME || ' ' || c.C_LAST_NAME AS CUSTOMER_NAME,
        c.C_EMAIL_ADDRESS,
        i.I_PRODUCT_NAME,
        i.I_CATEGORY,
        i.I_ITEM_SK,
        ss.ss_sales_price AS sales_price,
        d.D_DATE AS PURCHASE_DATE
    FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
    JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
        ON c.C_CUSTOMER_SK = ss.SS_CUSTOMER_SK
    JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
        ON i.I_ITEM_SK = ss.SS_ITEM_SK
    LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.DATE_DIM d
        ON d.D_DATE_SK = ss.SS_SOLD_DATE_SK
    ORDER BY d.D_DATE DESC, RANDOM()
    LIMIT 20
    """
    
    conn = get_snowflake_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Extract column names from the cursor description to construct JSON dictionaries
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        
        # Convert each row tuple into a dictionary using the column names
        orders = [dict(zip(columns, row)) for row in rows]
        
        return {"orders": orders}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")
    finally:
        conn.close()
