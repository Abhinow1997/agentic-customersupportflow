CREATE OR REPLACE TABLE SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS (
    
    -- Primary Identifiers
    ENQ_ID NUMBER(38,0) NOT NULL AUTOINCREMENT START 1 INCREMENT 1 NOORDER,
    ENQ_TICKET_NUMBER VARCHAR(20) NOT NULL UNIQUE,
    
    -- Customer Information
    ENQ_CUSTOMER_SK NUMBER(38,0),
    ENQ_CUSTOMER_EMAIL VARCHAR(100) NOT NULL,
    ENQ_CUSTOMER_NAME VARCHAR(200),
    
    -- Ticket Content
    ENQ_SUBJECT VARCHAR(500) NOT NULL,
    ENQ_BODY TEXT NOT NULL,
    ENQ_CHANNEL VARCHAR(20) NOT NULL DEFAULT 'email',
        -- Values: 'email', 'voicemail', 'web_form', 'chat'
    
    -- Classification (3 Main Categories)
    ENQ_CATEGORY VARCHAR(50),
        -- Values: 'order_delivery', 'returns_refunds', 'billing_payment'
    ENQ_SUBCATEGORY VARCHAR(50),
        -- order_delivery: 'late_delivery', 'wrong_item', 'damaged_package', 'not_received'
        -- returns_refunds: 'return_policy', 'refund_status', 'return_shipping', 'exchange'
        -- billing_payment: 'double_charge', 'fraud_concern', 'payment_declined', 'promo_issue'
    
    -- Status & Assignment
    ENQ_STATUS VARCHAR(20) DEFAULT 'Open',
        -- Values: 'Open', 'In Progress', 'Resolved', 'Closed'
    ENQ_PRIORITY VARCHAR(20) DEFAULT 'Medium',
        -- Values: 'Low', 'Medium', 'High', 'Critical'
    ENQ_ASSIGNED_TO VARCHAR(100),
    
    -- Resolution
    ENQ_RESOLUTION TEXT,
    ENQ_RESOLVED_AT TIMESTAMP_NTZ(9),
    ENQ_RESOLUTION_TIME_MINUTES NUMBER(10,2),
    
    -- Timestamps
    ENQ_CREATED_AT TIMESTAMP_NTZ(9) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    ENQ_UPDATED_AT TIMESTAMP_NTZ(9) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    
    -- ========== SNOWFLAKE CORTEX AI COLUMNS ==========
    
    -- Sentiment Analysis (CORTEX.SENTIMENT)
    ENQ_SENTIMENT_SCORE FLOAT,
        -- Range: -1.0 (very negative) to +1.0 (very positive)
    ENQ_SENTIMENT_LABEL VARCHAR(20),
        -- Values: 'Very Negative', 'Negative', 'Neutral', 'Positive', 'Very Positive'
    
    -- Urgency Score (computed from sentiment + keywords)
    ENQ_URGENCY_SCORE NUMBER(1,0),
        -- Range: 1 (low) to 5 (critical)
    
    -- Auto-Classification Confidence (CORTEX.COMPLETE)
    ENQ_CLASSIFICATION_CONFIDENCE FLOAT,
        -- Range: 0.0 to 1.0
    
    -- Vector Embedding for Semantic Search (CORTEX.EMBED_TEXT_768)
    ENQ_EMBEDDING VECTOR(FLOAT, 768),
    
    -- AI-Generated Summary (CORTEX.SUMMARIZE)
    ENQ_AI_SUMMARY VARCHAR(1000),
    
    -- AI-Suggested Response (CORTEX.COMPLETE)
    ENQ_SUGGESTED_RESPONSE TEXT,
    
    -- Channel-Specific Metadata
    ENQ_VOICEMAIL_REFERENCE VARCHAR(500),
    ENQ_VOICEMAIL_DURATION_SEC NUMBER(10,2),
    ENQ_EMAIL_THREAD_ID VARCHAR(200),
    
    -- Constraints
    PRIMARY KEY (ENQ_ID),
    FOREIGN KEY (ENQ_CUSTOMER_SK) 
        REFERENCES SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER(C_CUSTOMER_SK)
        
) COMMENT = 'Customer enquiry tickets with Snowflake Cortex AI enrichment. Categories: order_delivery, returns_refunds, billing_payment';



-- ============================================================================
-- FUNCTION: Intelligent Classification (VARIANT return, mixtral-8x7b)
-- ============================================================================

CREATE OR REPLACE FUNCTION SYNTHETIC_COMPANYDB.COMPANY.classify_enquiry_intelligent(
    subject STRING,
    body STRING
)
RETURNS VARIANT
LANGUAGE SQL
AS
$$
    WITH llm_analysis AS (
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'mixtral-8x7b',
            CONCAT(
                'You are an expert customer service analyzer for Walmart.

Analyze this customer enquiry and provide structured classification with reasoning.

**Categories:**
- billing_payment: Charges, fraud, payment issues, promotional discounts
- returns_refunds: Return process, refund status, return shipping, exchanges  
- order_delivery: Tracking, late delivery, wrong/damaged items, non-receipt

**Subcategories:**
billing_payment: double_charge, fraud_concern, payment_declined, promo_issue
returns_refunds: return_policy, refund_status, return_shipping, exchange
order_delivery: late_delivery, wrong_item, damaged_package, not_received

**Urgency Factors:**
- Time elapsed (e.g., "3 weeks ago" vs "yesterday")
- Time sensitivity (e.g., "need by Friday" vs "whenever")
- Repeat contact (e.g., "3rd time reaching out")
- Financial impact (e.g., "$500 charge" vs "$5")
- Emotional distress level
- Issue severity (fraud vs tracking question)

**Customer Message:**
Subject: ', subject, '
Body: ', body, '

Respond ONLY with valid JSON (no markdown, no backticks):
{
  "category": "billing_payment",
  "subcategory": "fraud_concern",
  "confidence": 0.95,
  "reasoning": "Customer reports unauthorized charge",
  "urgency_level": 5,
  "urgency_reasoning": "Fraud concern requires immediate attention",
  "extracted_entities": {
    "order_number": "12345",
    "amount": "150.00",
    "days_waiting": 7,
    "is_repeat_contact": false
  },
  "key_concerns": ["fraud_risk", "time_sensitive"]
}'
            )
        ) AS raw_response
    )
    SELECT 
        TRY_PARSE_JSON(
            REGEXP_REPLACE(raw_response, '```json|```', '')
        ) AS result
    FROM llm_analysis
$$;

-- ============================================================================
-- FUNCTION: Contextual Sentiment (VARIANT return, mixtral-8x7b)
-- ============================================================================

CREATE OR REPLACE FUNCTION SYNTHETIC_COMPANYDB.COMPANY.analyze_sentiment_contextual(
    subject STRING,
    body STRING,
    classification VARIANT  -- ✅ Changed from OBJECT to VARIANT
)
RETURNS VARIANT  -- ✅ Changed from OBJECT to VARIANT
LANGUAGE SQL
AS
$$
    WITH base_sentiment AS (
        SELECT SNOWFLAKE.CORTEX.SENTIMENT(subject || '. ' || body) AS score
    ),
    contextual_analysis AS (
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'mixtral-8x7b',  -- ✅ Changed from mistral-large2
            CONCAT(
                'Analyze the emotional state and frustration level of this customer.

Consider:
- Emotional state (angry, frustrated, confused, neutral, satisfied)
- Frustration level (1-5)
- Trust level in company (high, medium, low)
- Tone (professional, demanding, polite, threatening, casual)
- Churn risk (likely to stop being a customer)

**Customer Message:**
Subject: ', subject, '
Body: ', body, '

**Issue Type:** ', classification['category']::STRING, ' - ', classification['subcategory']::STRING, '

Respond ONLY with JSON (no markdown):
{
  "emotional_state": "frustrated",
  "frustration_level": 4,
  "trust_level": "medium",
  "tone": "demanding",
  "churn_risk": true,
  "reasoning": "Customer shows high frustration due to delay"
}'
            )
        ) AS raw_response,
        score
        FROM base_sentiment
    )
    SELECT 
        OBJECT_CONSTRUCT(
            'sentiment_score', score,
            'sentiment_label', 
                CASE 
                    WHEN score < -0.6 THEN 'Very Negative'
                    WHEN score < -0.2 THEN 'Negative'
                    WHEN score < 0.2  THEN 'Neutral'
                    WHEN score < 0.6  THEN 'Positive'
                    ELSE 'Very Positive'
                END,
            'contextual', TRY_PARSE_JSON(
                REGEXP_REPLACE(raw_response, '```json|```', '')
            )
        )::VARIANT AS result  -- ✅ Explicit cast to VARIANT
    FROM contextual_analysis
$$;



-- ============================================================================
-- PROCEDURE: Complete Intelligent Ticket Enrichment
-- ============================================================================

CREATE OR REPLACE FUNCTION SYNTHETIC_COMPANYDB.COMPANY.calculate_smart_urgency(
    classification VARIANT,
    sentiment VARIANT
)
RETURNS VARIANT
LANGUAGE SQL
AS
$$
    WITH urgency_factors AS (
        SELECT
            classification['category']::STRING AS category,
            classification['urgency_level']::INT AS llm_urgency,
            classification['extracted_entities']['is_repeat_contact']::BOOLEAN AS is_repeat,
            classification['extracted_entities']['days_waiting']::INT AS days_waiting,
            classification['extracted_entities']['amount']::FLOAT AS amount,
            classification['key_concerns'] AS concerns,
            
            sentiment['sentiment_score']::FLOAT AS sentiment_score,
            sentiment['contextual']['frustration_level']::INT AS frustration,
            sentiment['contextual']['churn_risk']::BOOLEAN AS churn_risk,
            sentiment['contextual']['emotional_state']::STRING AS emotion
    ),
    urgency_calc AS (
        SELECT 
            llm_urgency AS base_urgency,
            
            CASE 
                WHEN ARRAY_CONTAINS('fraud_risk'::VARIANT, concerns) THEN 2
                WHEN category = 'billing_payment' THEN 1
                ELSE 0
            END AS category_boost,
            
            CASE WHEN is_repeat = TRUE THEN 1 ELSE 0 END AS repeat_boost,
            
            CASE
                WHEN days_waiting >= 14 THEN 1
                WHEN days_waiting >= 7 THEN 0.5
                ELSE 0
            END AS wait_boost,
            
            CASE
                WHEN churn_risk = TRUE THEN 1
                WHEN emotion = 'angry' THEN 0.5
                ELSE 0
            END AS emotion_boost,
            
            CASE
                WHEN amount >= 500 THEN 1
                WHEN amount >= 200 THEN 0.5
                ELSE 0
            END AS value_boost,
            
            LEAST(5, GREATEST(1, 
                llm_urgency + 
                category_boost + 
                repeat_boost + 
                wait_boost + 
                emotion_boost + 
                value_boost
            )) AS final_urgency,
            
            CONCAT(
                'Base: ', llm_urgency,
                CASE WHEN category_boost > 0 THEN ' +' || category_boost || ' (billing/fraud)' ELSE '' END,
                CASE WHEN repeat_boost > 0 THEN ' +1 (repeat contact)' ELSE '' END,
                CASE WHEN wait_boost > 0 THEN ' +' || wait_boost || ' (long wait)' ELSE '' END,
                CASE WHEN emotion_boost > 0 THEN ' +' || emotion_boost || ' (churn risk)' ELSE '' END,
                CASE WHEN value_boost > 0 THEN ' +' || value_boost || ' (high value)' ELSE '' END
            ) AS urgency_reasoning
            
        FROM urgency_factors
    )
    SELECT 
        OBJECT_CONSTRUCT(
            'urgency_score', final_urgency::INT,
            'urgency_reasoning', urgency_reasoning,
            'urgency_factors', OBJECT_CONSTRUCT(
                'llm_base', base_urgency,
                'category_boost', category_boost,
                'repeat_contact', repeat_boost,
                'wait_time', wait_boost,
                'emotion', emotion_boost,
                'transaction_value', value_boost
            )
        )::VARIANT AS result
    FROM urgency_calc
$$;



CREATE OR REPLACE PROCEDURE SYNTHETIC_COMPANYDB.COMPANY.enrich_enquiry_intelligent(
    ticket_number STRING
)
RETURNS VARIANT
LANGUAGE SQL
AS
$$
DECLARE
    subject_text STRING;
    body_text STRING;
    classification VARIANT;
    sentiment VARIANT;
    urgency VARIANT;
    priority STRING;
    result_summary VARIANT;
BEGIN
    SELECT ENQ_SUBJECT, ENQ_BODY
    INTO subject_text, body_text
    FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
    WHERE ENQ_TICKET_NUMBER = :ticket_number;
    
    SELECT SYNTHETIC_COMPANYDB.COMPANY.classify_enquiry_intelligent(
        :subject_text, 
        :body_text
    )
    INTO classification;
    
    SELECT SYNTHETIC_COMPANYDB.COMPANY.analyze_sentiment_contextual(
        :subject_text, 
        :body_text, 
        :classification
    )
    INTO sentiment;
    
    SELECT SYNTHETIC_COMPANYDB.COMPANY.calculate_smart_urgency(
        :classification, 
        :sentiment
    )
    INTO urgency;
    
    SELECT 
        CASE
            WHEN urgency['urgency_score']::INT >= 5 THEN 'Critical'
            WHEN urgency['urgency_score']::INT >= 4 THEN 'High'
            WHEN urgency['urgency_score']::INT >= 3 THEN 'Medium'
            ELSE 'Low'
        END
    INTO priority;
    
    UPDATE SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
    SET 
        ENQ_CATEGORY = classification['category']::STRING,
        ENQ_SUBCATEGORY = classification['subcategory']::STRING,
        ENQ_CLASSIFICATION_CONFIDENCE = classification['confidence']::FLOAT,
        
        ENQ_SENTIMENT_SCORE = sentiment['sentiment_score']::FLOAT,
        ENQ_SENTIMENT_LABEL = sentiment['sentiment_label']::STRING,
        
        ENQ_URGENCY_SCORE = urgency['urgency_score']::INT,
        
        ENQ_PRIORITY = :priority,
        ENQ_UPDATED_AT = CURRENT_TIMESTAMP()
    WHERE ENQ_TICKET_NUMBER = :ticket_number;
    
    result_summary := OBJECT_CONSTRUCT(
        'ticket_number', :ticket_number,
        'category', classification['category']::STRING,
        'subcategory', classification['subcategory']::STRING,
        'priority', :priority,
        'urgency_score', urgency['urgency_score']::INT,
        'sentiment', sentiment['sentiment_label']::STRING,
        'classification_reasoning', classification['reasoning']::STRING,
        'urgency_reasoning', urgency['urgency_reasoning']::STRING,
        'extracted_entities', classification['extracted_entities'],
        'key_concerns', classification['key_concerns'],
        'emotional_state', sentiment['contextual']['emotional_state']::STRING,
        'churn_risk', sentiment['contextual']['churn_risk']::BOOLEAN
    )::VARIANT;
    
    RETURN result_summary;
END;
$$;



INSERT INTO SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS (
    ENQ_TICKET_NUMBER, ENQ_CUSTOMER_EMAIL, ENQ_CUSTOMER_NAME,
    ENQ_SUBJECT, ENQ_BODY, ENQ_CHANNEL
) VALUES (
    'TEST001',
    'test@test.com',
    'Test User',
    'Urgent fraud alert',
    'I see a $500 charge I did not authorize. This is fraud!',
    'email'
);

CALL SYNTHETIC_COMPANYDB.COMPANY.enrich_enquiry_intelligent('TEST001');

SELECT * FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS 
WHERE ENQ_TICKET_NUMBER = 'TEST001';
