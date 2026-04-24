-- ============================================================
-- EDA ANALYSIS: SYNTHETIC_COMPANYDB.COMPANY
-- ============================================================

-- Q1: Executive Snapshot — Key Business KPIs
SELECT
    (SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER)           AS total_customers,
    (SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.ITEM)               AS total_items,
    (SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES)        AS total_transactions,
    (SELECT SUM(SS_NET_PAID) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES) AS total_revenue,
    (SELECT SUM(SS_NET_PROFIT) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES) AS total_net_profit,
    (SELECT AVG(SS_NET_PAID) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES) AS avg_order_value,
    (SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS)      AS total_returns,
    ROUND((SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS) * 100.0
        / NULLIF((SELECT COUNT(*) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES), 0), 2) AS return_rate_pct,
    (SELECT AVG(SR_RETURN_AMT) FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS) AS avg_return_amount;


-- Q2: Revenue by Month — Monthly Trend with MoM % Change
WITH monthly AS (
    SELECT
        DATE_TRUNC('MONTH', d.D_DATE)                AS sale_month,
        COUNT(*)                                      AS order_count,
        SUM(ss.SS_NET_PAID)                           AS revenue,
        AVG(ss.SS_NET_PAID)                           AS avg_basket_size,
        SUM(ss.SS_NET_PROFIT)                         AS net_profit
    FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
    JOIN SYNTHETIC_COMPANYDB.COMPANY.DATE_DIM d
        ON ss.SS_SOLD_DATE_SK = d.D_DATE_SK
    GROUP BY DATE_TRUNC('MONTH', d.D_DATE)
)
SELECT
    sale_month,
    order_count,
    ROUND(revenue, 2)         AS revenue,
    ROUND(avg_basket_size, 2) AS avg_basket_size,
    ROUND(net_profit, 2)      AS net_profit,
    ROUND((revenue - LAG(revenue) OVER (ORDER BY sale_month))
        / NULLIF(LAG(revenue) OVER (ORDER BY sale_month), 0) * 100, 2) AS mom_change_pct
FROM monthly
ORDER BY sale_month;


-- Q3: Customer Segmentation by Spend Tier
WITH customer_spend AS (
    SELECT
        SS_CUSTOMER_SK,
        SUM(SS_NET_PAID) AS total_spend
    FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES
    WHERE SS_CUSTOMER_SK IS NOT NULL
    GROUP BY SS_CUSTOMER_SK
),
tiers AS (
    SELECT
        *,
        CASE
            WHEN total_spend >= PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total_spend) OVER () THEN 'High'
            WHEN total_spend >= PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total_spend) OVER () THEN 'Medium'
            ELSE 'Low'
        END AS spend_tier
    FROM customer_spend
)
SELECT
    spend_tier,
    COUNT(*)                                    AS customer_count,
    ROUND(AVG(total_spend), 2)                  AS avg_spend,
    ROUND(SUM(total_spend), 2)                  AS tier_revenue,
    ROUND(SUM(total_spend) * 100.0
        / SUM(SUM(total_spend)) OVER (), 2)     AS pct_of_total_revenue
FROM tiers
GROUP BY spend_tier
ORDER BY tier_revenue DESC;


-- Q4: Top 10 Revenue-Driving Categories
SELECT
    i.I_CATEGORY,
    COUNT(*)                                                    AS units_sold,
    ROUND(SUM(ss.SS_NET_PAID), 2)                               AS revenue,
    ROUND(AVG(ss.SS_SALES_PRICE), 2)                            AS avg_selling_price,
    ROUND(SUM(ss.SS_NET_PROFIT), 2)                             AS net_profit,
    ROUND(SUM(ss.SS_NET_PROFIT) * 100.0
        / NULLIF(SUM(ss.SS_NET_PAID), 0), 2)                    AS profit_margin_pct
FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
    ON ss.SS_ITEM_SK = i.I_ITEM_SK
GROUP BY i.I_CATEGORY
ORDER BY revenue DESC
LIMIT 10;


-- Q5: Return Rate by Category
WITH sales_by_cat AS (
    SELECT i.I_CATEGORY, COUNT(*) AS sold_count
    FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
    JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i ON ss.SS_ITEM_SK = i.I_ITEM_SK
    GROUP BY i.I_CATEGORY
),
returns_by_cat AS (
    SELECT i.I_CATEGORY, COUNT(*) AS return_count, ROUND(AVG(sr.SR_RETURN_AMT), 2) AS avg_return_amt
    FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS sr
    JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i ON sr.SR_ITEM_SK = i.I_ITEM_SK
    GROUP BY i.I_CATEGORY
)
SELECT
    s.I_CATEGORY,
    s.sold_count,
    COALESCE(r.return_count, 0)                                          AS return_count,
    ROUND(COALESCE(r.return_count, 0) * 100.0 / NULLIF(s.sold_count, 0), 2) AS return_rate_pct,
    COALESCE(r.avg_return_amt, 0)                                        AS avg_return_amt
FROM sales_by_cat s
LEFT JOIN returns_by_cat r ON s.I_CATEGORY = r.I_CATEGORY
ORDER BY return_rate_pct DESC;


-- Q6: Customer Lifetime Value (CLV) Distribution — Top 50
SELECT
    ss.SS_CUSTOMER_SK,
    c.C_FIRST_NAME,
    c.C_LAST_NAME,
    COUNT(*)                         AS order_count,
    ROUND(SUM(ss.SS_NET_PAID), 2)    AS total_spend,
    ROUND(AVG(ss.SS_NET_PAID), 2)    AS avg_order_value,
    MIN(d.D_DATE)                    AS first_purchase,
    MAX(d.D_DATE)                    AS last_purchase,
    DATEDIFF('day', MIN(d.D_DATE), MAX(d.D_DATE)) AS tenure_days
FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
    ON ss.SS_CUSTOMER_SK = c.C_CUSTOMER_SK
JOIN SYNTHETIC_COMPANYDB.COMPANY.DATE_DIM d
    ON ss.SS_SOLD_DATE_SK = d.D_DATE_SK
WHERE ss.SS_CUSTOMER_SK IS NOT NULL
GROUP BY ss.SS_CUSTOMER_SK, c.C_FIRST_NAME, c.C_LAST_NAME
ORDER BY total_spend DESC
LIMIT 50;


-- Q7: Geographic Revenue Heatmap — Revenue by State
SELECT
    ca.CA_STATE,
    COUNT(DISTINCT ss.SS_CUSTOMER_SK) AS customer_count,
    COUNT(*)                          AS transaction_count,
    ROUND(SUM(ss.SS_NET_PAID), 2)     AS revenue,
    ROUND(AVG(ss.SS_NET_PAID), 2)     AS avg_spend_per_txn,
    ROUND(SUM(ss.SS_NET_PAID) / NULLIF(COUNT(DISTINCT ss.SS_CUSTOMER_SK), 0), 2) AS revenue_per_customer
FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
    ON ss.SS_CUSTOMER_SK = c.C_CUSTOMER_SK
JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER_ADDRESS ca
    ON c.C_CURRENT_ADDR_SK = ca.CA_ADDRESS_SK
WHERE ss.SS_CUSTOMER_SK IS NOT NULL
GROUP BY ca.CA_STATE
ORDER BY revenue DESC;


-- Q8: Discount & Margin Analysis by Category
SELECT
    i.I_CATEGORY,
    COUNT(*)                                                                       AS txn_count,
    ROUND(AVG(ss.SS_EXT_DISCOUNT_AMT / NULLIF(ss.SS_EXT_LIST_PRICE, 0)) * 100, 2) AS avg_discount_pct,
    ROUND(AVG((ss.SS_EXT_SALES_PRICE - ss.SS_EXT_WHOLESALE_COST)
        / NULLIF(ss.SS_EXT_SALES_PRICE, 0)) * 100, 2)                              AS gross_margin_pct,
    ROUND(AVG(ss.SS_NET_PROFIT / NULLIF(ss.SS_NET_PAID, 0)) * 100, 2)              AS net_margin_pct,
    ROUND(SUM(ss.SS_COUPON_AMT), 2)                                                AS total_coupon_amt
FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
    ON ss.SS_ITEM_SK = i.I_ITEM_SK
GROUP BY i.I_CATEGORY
ORDER BY net_margin_pct ASC;


-- Q9: Return Reasons Breakdown
SELECT
    sr.SR_REASON_DESC,
    COUNT(*)                        AS return_count,
    ROUND(SUM(sr.SR_RETURN_AMT), 2) AS total_return_amt,
    ROUND(AVG(sr.SR_RETURN_AMT), 2) AS avg_return_amt,
    ROUND(SUM(sr.SR_NET_LOSS), 2)   AS total_net_loss,
    ROUND(AVG(sr.SR_NET_LOSS), 2)   AS avg_net_loss
FROM SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS sr
GROUP BY sr.SR_REASON_DESC
ORDER BY total_net_loss DESC;


-- Q10: Customer Support Health
SELECT
    ENQ_CATEGORY,
    ENQ_PRIORITY,
    COUNT(*)                                        AS ticket_count,
    ROUND(AVG(ENQ_SENTIMENT_SCORE), 3)              AS avg_sentiment,
    SUM(CASE WHEN ENQ_SENTIMENT_LABEL = 'Negative' THEN 1 ELSE 0 END) AS negative_tickets,
    ROUND(AVG(ENQ_RESOLUTION_TIME_MINUTES), 2)      AS avg_resolution_min,
    SUM(CASE WHEN ENQ_STATUS = 'Open' THEN 1 ELSE 0 END)    AS open_count,
    SUM(CASE WHEN ENQ_STATUS = 'Resolved' THEN 1 ELSE 0 END) AS resolved_count
FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
GROUP BY ENQ_CATEGORY, ENQ_PRIORITY
ORDER BY ticket_count DESC;
