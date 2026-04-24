-- ============================================================================
-- CORTEX-POWERED ENQUIRY TICKET SYSTEM
-- ============================================================================

-- Main Enquiry Tickets Table
CREATE OR REPLACE TABLE SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS (
    -- Primary Identifiers
    ENQ_ID NUMBER(38,0) NOT NULL AUTOINCREMENT START 1 INCREMENT 1 NOORDER,
    ENQ_TICKET_NUMBER VARCHAR(20) NOT NULL UNIQUE,
    
    -- Customer Information
    ENQ_CUSTOMER_SK NUMBER(38,0),
    ENQ_CUSTOMER_EMAIL VARCHAR(100),
    ENQ_CUSTOMER_NAME VARCHAR(200),
    
    -- Ticket Content
    ENQ_SUBJECT VARCHAR(500) NOT NULL,
    ENQ_BODY TEXT NOT NULL,
    ENQ_CHANNEL VARCHAR(20) NOT NULL, -- 'email', 'voicemail', 'chat', 'web_form'
    
    -- Channel-Specific Metadata
    ENQ_VOICEMAIL_S3_KEY VARCHAR(500),
    ENQ_VOICEMAIL_DURATION_SEC NUMBER(10,2),
    ENQ_EMAIL_THREAD_ID VARCHAR(200),
    
    -- Status & Assignment
    ENQ_STATUS VARCHAR(20) DEFAULT 'Open', -- 'Open', 'In Progress', 'Resolved', 'Closed'
    ENQ_PRIORITY VARCHAR(20) DEFAULT 'Medium', -- 'Low', 'Medium', 'High', 'Critical'
    ENQ_ASSIGNED_TO VARCHAR(100),
    ENQ_DEPARTMENT VARCHAR(50), -- 'billing', 'technical', 'general', 'returns'
    
    -- Resolution
    ENQ_RESOLUTION TEXT,
    ENQ_RESOLVED_AT TIMESTAMP_NTZ(9),
    ENQ_RESOLUTION_TIME_MINUTES NUMBER(10,2),
    
    -- Timestamps
    ENQ_CREATED_AT TIMESTAMP_NTZ(9) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    ENQ_UPDATED_AT TIMESTAMP_NTZ(9) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    
    -- ========== SNOWFLAKE CORTEX ENRICHMENT COLUMNS ==========
    
    -- Sentiment Analysis
    ENQ_SENTIMENT_SCORE FLOAT, -- -1 to 1 from CORTEX.SENTIMENT()
    ENQ_SENTIMENT_LABEL VARCHAR(20), -- 'Very Negative', 'Negative', 'Neutral', 'Positive', 'Very Positive'
    
    -- Urgency Classification
    ENQ_URGENCY_SCORE NUMBER(3,0), -- 1-5 computed from sentiment + keywords
    ENQ_URGENCY_KEYWORDS ARRAY, -- Keywords detected: ['urgent', 'asap', 'immediately']
    
    -- Category Classification
    ENQ_CATEGORY VARCHAR(50), -- Auto-classified: 'billing', 'shipping', 'product_issue', 'account', 'general'
    ENQ_SUBCATEGORY VARCHAR(50),
    ENQ_CLASSIFICATION_CONFIDENCE FLOAT, -- 0-1 confidence score
    
    -- Vector Embeddings for Semantic Search
    ENQ_EMBEDDING VECTOR(FLOAT, 768), -- e5-base-v2 embedding
    
    -- AI-Generated Summary
    ENQ_AI_SUMMARY VARCHAR(1000), -- CORTEX.SUMMARIZE() output
    
    -- Suggested Actions (from CORTEX.COMPLETE)
    ENQ_SUGGESTED_ACTIONS ARRAY, -- ['issue_refund', 'send_replacement', 'escalate']
    ENQ_SUGGESTED_RESPONSE TEXT, -- AI-drafted response
    
    -- Similar Tickets (pre-computed on insert)
    ENQ_SIMILAR_TICKET_IDS ARRAY, -- Top 3 similar resolved ticket numbers
    ENQ_SIMILAR_TICKET_SCORES ARRAY, -- Cosine similarity scores
    
    -- Quality & Compliance
    ENQ_CONTAINS_PII BOOLEAN DEFAULT FALSE, -- Detected via pattern matching
    ENQ_LANGUAGE VARCHAR(10) DEFAULT 'en', -- Detected language code
    ENQ_TRANSLATION_NEEDED BOOLEAN DEFAULT FALSE,
    
    PRIMARY KEY (ENQ_ID),
    FOREIGN KEY (ENQ_CUSTOMER_SK) REFERENCES SYNTHETIC_COMPANYDB.COMPANY.CUSTOMER(C_CUSTOMER_SK)
)
COMMENT = 'Customer enquiry tickets with Snowflake Cortex AI enrichment';


-- Enquiry Interaction History (for multi-turn conversations)
CREATE OR REPLACE TABLE SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_INTERACTIONS (
    INT_ID NUMBER(38,0) NOT NULL AUTOINCREMENT START 1 INCREMENT 1 NOORDER,
    INT_ENQ_TICKET_NUMBER VARCHAR(20) NOT NULL,
    
    -- Interaction Details
    INT_SENDER_TYPE VARCHAR(20) NOT NULL, -- 'customer', 'agent', 'system'
    INT_SENDER_NAME VARCHAR(200),
    INT_MESSAGE TEXT NOT NULL,
    INT_TIMESTAMP TIMESTAMP_NTZ(9) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    
    -- Cortex Analysis (per message)
    INT_SENTIMENT_SCORE FLOAT,
    INT_IS_QUESTION BOOLEAN, -- Detected via CORTEX pattern
    INT_EXTRACTED_ENTITIES VARIANT, -- JSON: {"order_id": "123", "amount": "$50"}
    
    PRIMARY KEY (INT_ID)
)
COMMENT = 'Interaction history for multi-turn enquiry conversations';


-- Enquiry Status History (audit trail)
CREATE OR REPLACE TABLE SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_STATUS_HISTORY (
    ESH_ID NUMBER(38,0) NOT NULL AUTOINCREMENT START 1 INCREMENT 1 NOORDER,
    ESH_ENQ_TICKET_NUMBER VARCHAR(20) NOT NULL,
    
    ESH_OLD_STATUS VARCHAR(20),
    ESH_NEW_STATUS VARCHAR(20) NOT NULL,
    ESH_CHANGED_BY VARCHAR(100) DEFAULT 'system',
    ESH_CHANGED_AT TIMESTAMP_NTZ(9) NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    ESH_NOTE VARCHAR(500),
    
    PRIMARY KEY (ESH_ID)
)
COMMENT = 'Status change audit trail for enquiry tickets';


-- ============================================================================
-- CORTEX-POWERED FUNCTIONS
-- ============================================================================

-- Function: Classify Enquiry Category
CREATE OR REPLACE FUNCTION classify_enquiry_category(enquiry_text STRING)
RETURNS TABLE (
    category STRING,
    subcategory STRING,
    confidence FLOAT
)
AS
$$
    WITH classification AS (
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'mistral-large2',
            CONCAT(
                'Classify this customer enquiry into ONE category. Respond ONLY with valid JSON in this exact format: {"category": "billing|shipping|product_issue|account|returns|general", "subcategory": "refund|tracking|defect|password_reset|size_exchange|other", "confidence": 0.95}
                
Customer enquiry: ', enquiry_text
            )
        ) AS raw_response
    )
    SELECT 
        PARSE_JSON(REGEXP_REPLACE(raw_response, '```json|```', ''))['category']::STRING AS category,
        PARSE_JSON(REGEXP_REPLACE(raw_response, '```json|```', ''))['subcategory']::STRING AS subcategory,
        PARSE_JSON(REGEXP_REPLACE(raw_response, '```json|```', ''))['confidence']::FLOAT AS confidence
    FROM classification
$$;


-- Function: Find Similar Enquiries
CREATE OR REPLACE FUNCTION find_similar_enquiries(
    query_embedding VECTOR(FLOAT, 768),
    limit_count INT DEFAULT 5
)
RETURNS TABLE (
    ticket_number STRING,
    similarity_score FLOAT,
    subject STRING,
    resolution STRING,
    category STRING
)
AS
$$
    SELECT 
        ENQ_TICKET_NUMBER AS ticket_number,
        VECTOR_COSINE_SIMILARITY(ENQ_EMBEDDING, query_embedding) AS similarity_score,
        ENQ_SUBJECT AS subject,
        ENQ_RESOLUTION AS resolution,
        ENQ_CATEGORY AS category
    FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
    WHERE ENQ_STATUS IN ('Resolved', 'Closed')
      AND ENQ_RESOLUTION IS NOT NULL
      AND ENQ_EMBEDDING IS NOT NULL
    ORDER BY similarity_score DESC
    LIMIT limit_count
$$;


-- Function: Generate Resolution Suggestion
CREATE OR REPLACE FUNCTION suggest_enquiry_resolution(
    enquiry_subject STRING,
    enquiry_body STRING,
    similar_resolutions ARRAY
)
RETURNS STRING
AS
$$
    SNOWFLAKE.CORTEX.COMPLETE(
        'mistral-large2',
        CONCAT(
            'You are a customer support agent AI. Based on these similar past resolutions:

', ARRAY_TO_STRING(similar_resolutions, '

---

'),
            '

Draft a professional response (under 150 words) for this NEW enquiry:

Subject: ', enquiry_subject, '
Body: ', enquiry_body, '

Response (be helpful, empathetic, and actionable):'
        )
    )
$$;


-- Procedure: Full Cortex Enrichment Pipeline
CREATE OR REPLACE PROCEDURE enrich_enquiry_with_cortex(ticket_number STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    enquiry_text STRING;
    subject_text STRING;
    sentiment_val FLOAT;
    sentiment_lbl STRING;
    urgency_val INT;
    category_val STRING;
    subcategory_val STRING;
    confidence_val FLOAT;
    embedding_val VECTOR(FLOAT, 768);
    summary_val STRING;
    similar_ids ARRAY;
    similar_scores ARRAY;
    suggested_resp STRING;
BEGIN
    -- Get enquiry text
    SELECT ENQ_SUBJECT, ENQ_BODY 
    INTO subject_text, enquiry_text
    FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
    WHERE ENQ_TICKET_NUMBER = :ticket_number;
    
    LET combined_text STRING := subject_text || '. ' || enquiry_text;
    
    -- 1. Sentiment Analysis
    SELECT SNOWFLAKE.CORTEX.SENTIMENT(combined_text) INTO sentiment_val;
    
    SELECT CASE
        WHEN :sentiment_val < -0.7 THEN 'Very Negative'
        WHEN :sentiment_val < -0.3 THEN 'Negative'
        WHEN :sentiment_val < 0.3 THEN 'Neutral'
        WHEN :sentiment_val < 0.7 THEN 'Positive'
        ELSE 'Very Positive'
    END INTO sentiment_lbl;
    
    -- 2. Urgency Score (based on keywords + sentiment)
    LET urgency_keywords ARRAY := ARRAY_CONSTRUCT();
    IF (LOWER(combined_text) LIKE '%urgent%' OR LOWER(combined_text) LIKE '%asap%' OR LOWER(combined_text) LIKE '%immediately%') THEN
        urgency_keywords := ARRAY_CONSTRUCT('urgent', 'asap', 'immediately');
    END IF;
    
    SELECT CASE
        WHEN :sentiment_val < -0.7 AND ARRAY_SIZE(:urgency_keywords) > 0 THEN 5
        WHEN :sentiment_val < -0.5 THEN 4
        WHEN :sentiment_val < 0 THEN 3
        WHEN ARRAY_SIZE(:urgency_keywords) > 0 THEN 3
        ELSE 2
    END INTO urgency_val;
    
    -- 3. Category Classification
    SELECT category, subcategory, confidence 
    INTO category_val, subcategory_val, confidence_val
    FROM TABLE(classify_enquiry_category(:combined_text))
    LIMIT 1;
    
    -- 4. Generate Embedding
    SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768('e5-base-v2', :combined_text) INTO embedding_val;
    
    -- 5. Summarize
    SELECT SNOWFLAKE.CORTEX.SUMMARIZE(:combined_text) INTO summary_val;
    
    -- 6. Find Similar Tickets
    SELECT 
        ARRAY_AGG(ticket_number),
        ARRAY_AGG(similarity_score)
    INTO similar_ids, similar_scores
    FROM TABLE(find_similar_enquiries(:embedding_val, 3));
    
    -- 7. Generate Suggested Response
    IF (ARRAY_SIZE(:similar_ids) > 0) THEN
        LET similar_resolutions ARRAY;
        SELECT ARRAY_AGG(ENQ_RESOLUTION)
        INTO similar_resolutions
        FROM SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
        WHERE ENQ_TICKET_NUMBER IN (SELECT VALUE FROM TABLE(FLATTEN(:similar_ids)));
        
        SELECT suggest_enquiry_resolution(:subject_text, :enquiry_text, :similar_resolutions)
        INTO suggested_resp;
    ELSE
        suggested_resp := NULL;
    END IF;
    
    -- 8. Update Ticket with Cortex Enrichment
    UPDATE SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS
    SET 
        ENQ_SENTIMENT_SCORE = :sentiment_val,
        ENQ_SENTIMENT_LABEL = :sentiment_lbl,
        ENQ_URGENCY_SCORE = :urgency_val,
        ENQ_URGENCY_KEYWORDS = :urgency_keywords,
        ENQ_CATEGORY = :category_val,
        ENQ_SUBCATEGORY = :subcategory_val,
        ENQ_CLASSIFICATION_CONFIDENCE = :confidence_val,
        ENQ_EMBEDDING = :embedding_val,
        ENQ_AI_SUMMARY = :summary_val,
        ENQ_SIMILAR_TICKET_IDS = :similar_ids,
        ENQ_SIMILAR_TICKET_SCORES = :similar_scores,
        ENQ_SUGGESTED_RESPONSE = :suggested_resp,
        ENQ_UPDATED_AT = CURRENT_TIMESTAMP()
    WHERE ENQ_TICKET_NUMBER = :ticket_number;
    
    RETURN 'Cortex enrichment completed for ticket: ' || :ticket_number;
END;
$$;


-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_enq_status 
ON SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS(ENQ_STATUS);

CREATE INDEX IF NOT EXISTS idx_enq_category 
ON SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS(ENQ_CATEGORY);

CREATE INDEX IF NOT EXISTS idx_enq_customer 
ON SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS(ENQ_CUSTOMER_SK);

CREATE INDEX IF NOT EXISTS idx_enq_created 
ON SYNTHETIC_COMPANYDB.COMPANY.ENQUIRY_TICKETS(ENQ_CREATED_AT);
