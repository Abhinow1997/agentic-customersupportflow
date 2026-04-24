-- ============================================================
-- PROCEDURE 1: order_delivery_procedure
-- "Where is my order?" — Order details, shipping, delivery status
-- CALL SYNTHETIC_COMPANYDB.COMPANY.order_delivery_procedure('customer@example.com');
-- ============================================================
CREATE OR REPLACE PROCEDURE SYNTHETIC_COMPANYDB.COMPANY.order_delivery_procedure(customer_email VARCHAR)
RETURNS TABLE ()
LANGUAGE SQL
AS
DECLARE
    res RESULTSET DEFAULT (
        SELECT
            c.C_FIRST_NAME || ' ' || c.C_LAST_NAME   AS CUSTOMER_NAME,
            c.C_EMAIL_ADDRESS                          AS CUSTOMER_EMAIL,
            ss.SS_TICKET_NUMBER                        AS ORDER_TICKET,
            d.D_DATE                                   AS ORDER_DATE,
            i.I_PRODUCT_NAME                           AS ITEM_NAME,
            i.I_CATEGORY                               AS ITEM_CATEGORY,
            i.I_BRAND                                  AS ITEM_BRAND,
            ss.SS_QUANTITY                              AS QUANTITY,
            ss.SS_SALES_PRICE                          AS UNIT_PRICE,
            ss.SS_NET_PAID_INC_TAX                     AS AMOUNT_PAID,
            sm.SM_CARRIER                              AS SHIP_CARRIER,
            sm.SM_TYPE                                 AS SHIP_TYPE,
            sm.SM_CODE                                 AS SHIP_CODE,
            et.ENQ_TICKET_NUMBER                       AS ENQUIRY_TICKET,
            et.ENQ_STATUS                              AS ENQUIRY_STATUS,
            et.ENQ_PRIORITY                            AS ENQUIRY_PRIORITY,
            et.ENQ_AI_SUMMARY                          AS ENQUIRY_SUMMARY,
            et.ENQ_SUGGESTED_RESPONSE                  AS SUGGESTED_RESPONSE
        FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
        JOIN SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
            ON ss.SS_CUSTOMER_SK = c.C_CUSTOMER_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.DATE_DIM d
            ON d.D_DATE_SK = ss.SS_SOLD_DATE_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
            ON i.I_ITEM_SK = ss.SS_ITEM_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.SHIP_MODE sm
            ON sm.SM_SHIP_MODE_SK = ss.SS_SHIP_MODE_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS et
            ON et.ENQ_CUSTOMER_SK = c.C_CUSTOMER_SK
            AND et.ENQ_CATEGORY = 'order_delivery'
        WHERE c.C_EMAIL_ADDRESS = :customer_email
        ORDER BY d.D_DATE DESC
        LIMIT 20
    );
BEGIN
    RETURN TABLE(res);
END;


-- ============================================================
-- PROCEDURE 2: returns_refunds_procedure
-- "Where is my refund?" — Return status, refund decisions
-- CALL SYNTHETIC_COMPANYDB.COMPANY.returns_refunds_procedure('customer@example.com');
-- ============================================================
CREATE OR REPLACE PROCEDURE SYNTHETIC_COMPANYDB.COMPANY.returns_refunds_procedure(customer_email VARCHAR)
RETURNS TABLE ()
LANGUAGE SQL
AS
DECLARE
    res RESULTSET DEFAULT (
        SELECT
            c.C_FIRST_NAME || ' ' || c.C_LAST_NAME       AS CUSTOMER_NAME,
            c.C_EMAIL_ADDRESS                              AS CUSTOMER_EMAIL,
            sr.SR_TICKET_NUMBER                            AS RETURN_TICKET,
            sr.SR_RETURNED_DATE                            AS RETURN_DATE,
            sr.SR_STATUS                                   AS RETURN_STATUS,
            i.I_PRODUCT_NAME                               AS ITEM_NAME,
            i.I_CATEGORY                                   AS ITEM_CATEGORY,
            sr.SR_RETURN_QUANTITY                           AS RETURN_QTY,
            sr.SR_RETURN_AMT                               AS RETURN_AMOUNT,
            sr.SR_FEE                                      AS RETURN_FEE,
            sr.SR_NET_LOSS                                 AS NET_LOSS,
            sr.SR_REASON_DESC                              AS RETURN_REASON,
            rd.DECISION                                    AS REFUND_DECISION,
            rd.DECISION_NOTE                               AS DECISION_NOTE,
            rd.PACKAGING_CONDITION                         AS PACKAGING_CONDITION,
            rd.ASSESSMENT_SUMMARY                          AS ASSESSMENT_SUMMARY,
            rd.ASSESSMENT_CONFIDENCE                       AS ASSESSMENT_CONFIDENCE,
            CASE
                WHEN rd.DECISION = 'approved' AND sr.SR_STATUS = 'Closed' THEN 'Refund Processed'
                WHEN rd.DECISION = 'approved' AND sr.SR_STATUS = 'Open'   THEN 'Refund Approved - Pending'
                WHEN rd.DECISION = 'denied'                                THEN 'Refund Denied'
                WHEN rd.DECISION IS NULL AND sr.SR_STATUS = 'Open'        THEN 'Under Review'
                ELSE 'Unknown'
            END                                            AS REFUND_STATUS_SUMMARY,
            et.ENQ_TICKET_NUMBER                           AS ENQUIRY_TICKET,
            et.ENQ_STATUS                                  AS ENQUIRY_STATUS,
            et.ENQ_AI_SUMMARY                              AS ENQUIRY_SUMMARY,
            et.ENQ_SUGGESTED_RESPONSE                      AS SUGGESTED_RESPONSE
        FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
        JOIN SYNTHETIC_COMPANYDB.COMPANY.STORE_RETURNS sr
            ON sr.SR_CUSTOMER_SK = c.C_CUSTOMER_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
            ON i.I_ITEM_SK = sr.SR_ITEM_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.RETURN_DECISIONS rd
            ON rd.SR_TICKET_NUMBER = sr.SR_TICKET_NUMBER
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS et
            ON et.ENQ_CUSTOMER_SK = c.C_CUSTOMER_SK
            AND et.ENQ_CATEGORY = 'returns_refunds'
        WHERE c.C_EMAIL_ADDRESS = :customer_email
        ORDER BY sr.SR_RETURNED_DATE DESC
    );
BEGIN
    RETURN TABLE(res);
END;


-- ============================================================
-- PROCEDURE 3: billing_payment_procedure
-- "Billing or payment issue" — Purchase history, pricing, tax
-- CALL SYNTHETIC_COMPANYDB.COMPANY.billing_payment_procedure('customer@example.com');
-- ============================================================
CREATE OR REPLACE PROCEDURE SYNTHETIC_COMPANYDB.COMPANY.billing_payment_procedure(customer_email VARCHAR)
RETURNS TABLE ()
LANGUAGE SQL
AS
DECLARE
    res RESULTSET DEFAULT (
        SELECT
            c.C_FIRST_NAME || ' ' || c.C_LAST_NAME   AS CUSTOMER_NAME,
            c.C_EMAIL_ADDRESS                          AS CUSTOMER_EMAIL,
            ss.SS_TICKET_NUMBER                        AS ORDER_TICKET,
            d.D_DATE                                   AS ORDER_DATE,
            i.I_PRODUCT_NAME                           AS ITEM_NAME,
            ss.SS_QUANTITY                              AS QUANTITY,
            ss.SS_LIST_PRICE                           AS LIST_PRICE,
            ss.SS_SALES_PRICE                          AS SALES_PRICE,
            ss.SS_EXT_DISCOUNT_AMT                     AS DISCOUNT_AMOUNT,
            ss.SS_COUPON_AMT                           AS COUPON_AMOUNT,
            ss.SS_EXT_SALES_PRICE                      AS EXT_SALES_PRICE,
            ss.SS_EXT_TAX                              AS TAX_AMOUNT,
            ss.SS_NET_PAID                             AS NET_PAID,
            ss.SS_NET_PAID_INC_TAX                     AS NET_PAID_INC_TAX,
            ss.SS_NET_PROFIT                           AS NET_PROFIT,
            et.ENQ_TICKET_NUMBER                       AS ENQUIRY_TICKET,
            et.ENQ_STATUS                              AS ENQUIRY_STATUS,
            et.ENQ_PRIORITY                            AS ENQUIRY_PRIORITY,
            et.ENQ_AI_SUMMARY                          AS ENQUIRY_SUMMARY,
            et.ENQ_SUGGESTED_RESPONSE                  AS SUGGESTED_RESPONSE
        FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
        JOIN SYNTHETIC_COMPANYDB.COMPANY.STORE_SALES ss
            ON ss.SS_CUSTOMER_SK = c.C_CUSTOMER_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.DATE_DIM d
            ON d.D_DATE_SK = ss.SS_SOLD_DATE_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.ITEM i
            ON i.I_ITEM_SK = ss.SS_ITEM_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS et
            ON et.ENQ_CUSTOMER_SK = c.C_CUSTOMER_SK
            AND et.ENQ_CATEGORY = 'billing_payment'
        WHERE c.C_EMAIL_ADDRESS = :customer_email
        ORDER BY d.D_DATE DESC
        LIMIT 20
    );
BEGIN
    RETURN TABLE(res);
END;


-- ============================================================
-- PROCEDURE 4: account_management_procedure
-- "Update my account" — Profile, address, demographics
-- CALL SYNTHETIC_COMPANYDB.COMPANY.account_management_procedure('customer@example.com');
-- ============================================================
CREATE OR REPLACE PROCEDURE SYNTHETIC_COMPANYDB.COMPANY.account_management_procedure(customer_email VARCHAR)
RETURNS TABLE ()
LANGUAGE SQL
AS
DECLARE
    res RESULTSET DEFAULT (
        SELECT
            c.C_FIRST_NAME || ' ' || c.C_LAST_NAME   AS CUSTOMER_NAME,
            c.C_EMAIL_ADDRESS                          AS CUSTOMER_EMAIL,
            c.C_PREFERRED_CUST_FLAG                    AS PREFERRED_CUSTOMER,
            ca.CA_STREET_NUMBER || ' ' || ca.CA_STREET_NAME || ' ' || ca.CA_STREET_TYPE
                                                       AS STREET_ADDRESS,
            ca.CA_SUITE_NUMBER                         AS SUITE,
            ca.CA_CITY                                 AS CITY,
            ca.CA_STATE                                AS STATE,
            ca.CA_ZIP                                  AS ZIP,
            ca.CA_COUNTRY                              AS COUNTRY,
            cd.CD_GENDER                               AS GENDER,
            cd.CD_MARITAL_STATUS                       AS MARITAL_STATUS,
            cd.CD_EDUCATION_STATUS                     AS EDUCATION,
            cd.CD_CREDIT_RATING                        AS CREDIT_RATING,
            cd.CD_PURCHASE_ESTIMATE                    AS PURCHASE_ESTIMATE,
            et.ENQ_TICKET_NUMBER                       AS ENQUIRY_TICKET,
            et.ENQ_STATUS                              AS ENQUIRY_STATUS,
            et.ENQ_PRIORITY                            AS ENQUIRY_PRIORITY,
            et.ENQ_AI_SUMMARY                          AS ENQUIRY_SUMMARY,
            et.ENQ_SUGGESTED_RESPONSE                  AS SUGGESTED_RESPONSE
        FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER_ADDRESS ca
            ON ca.CA_ADDRESS_SK = c.C_CURRENT_ADDR_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER_DEMOGRAPHICS cd
            ON cd.CD_DEMO_SK = c.C_CURRENT_CDEMO_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS et
            ON et.ENQ_CUSTOMER_SK = c.C_CUSTOMER_SK
            AND et.ENQ_CATEGORY = 'account_management'
        WHERE c.C_EMAIL_ADDRESS = :customer_email
    );
BEGIN
    RETURN TABLE(res);
END;


-- ============================================================
-- PROCEDURE 5: general_enquiry_procedure
-- Catch-all — Enquiry details, sentiment, history, AI insights
-- CALL SYNTHETIC_COMPANYDB.COMPANY.general_enquiry_procedure('customer@example.com');
-- ============================================================
CREATE OR REPLACE PROCEDURE SYNTHETIC_COMPANYDB.COMPANY.general_enquiry_procedure(customer_email VARCHAR)
RETURNS TABLE ()
LANGUAGE SQL
AS
DECLARE
    res RESULTSET DEFAULT (
        SELECT
            c.C_FIRST_NAME || ' ' || c.C_LAST_NAME   AS CUSTOMER_NAME,
            c.C_EMAIL_ADDRESS                          AS CUSTOMER_EMAIL,
            et.ENQ_TICKET_NUMBER                       AS ENQUIRY_TICKET,
            et.ENQ_CATEGORY                            AS CATEGORY,
            et.ENQ_SUBCATEGORY                         AS SUBCATEGORY,
            et.ENQ_SUBJECT                             AS SUBJECT,
            et.ENQ_BODY                                AS BODY,
            et.ENQ_CHANNEL                             AS CHANNEL,
            et.ENQ_STATUS                              AS STATUS,
            et.ENQ_PRIORITY                            AS PRIORITY,
            et.ENQ_ASSIGNED_TO                         AS ASSIGNED_TO,
            et.ENQ_SENTIMENT_LABEL                     AS SENTIMENT,
            et.ENQ_SENTIMENT_SCORE                     AS SENTIMENT_SCORE,
            et.ENQ_URGENCY_SCORE                       AS URGENCY_SCORE,
            et.ENQ_AI_SUMMARY                          AS AI_SUMMARY,
            et.ENQ_SUGGESTED_RESPONSE                  AS SUGGESTED_RESPONSE,
            et.ENQ_RESOLUTION                          AS RESOLUTION,
            et.ENQ_RESOLVED_AT                         AS RESOLVED_AT,
            et.ENQ_RESOLUTION_TIME_MINUTES             AS RESOLUTION_MINUTES,
            et.ENQ_CREATED_AT                          AS CREATED_AT,
            tsh.TSH_OLD_STATUS                         AS PREV_STATUS,
            tsh.TSH_NEW_STATUS                         AS NEW_STATUS,
            tsh.TSH_CHANGED_AT                         AS STATUS_CHANGED_AT,
            tsh.TSH_NOTE                               AS STATUS_NOTE
        FROM SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER c
        JOIN SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS et
            ON et.ENQ_CUSTOMER_SK = c.C_CUSTOMER_SK
        LEFT JOIN SYNTHETIC_COMPANYDB.COMPANY.TICKET_STATUS_HISTORY tsh
            ON tsh.TSH_TICKET_NUMBER = et.ENQ_TICKET_NUMBER
        WHERE c.C_EMAIL_ADDRESS = :customer_email
        ORDER BY et.ENQ_CREATED_AT DESC
    );
BEGIN
    RETURN TABLE(res);
END;
