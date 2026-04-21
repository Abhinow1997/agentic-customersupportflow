# AI Client Instruction Set for `agentic-customersupportflow`

This document is a technical briefing for an AI client that needs to understand, operate on, or extend this codebase safely.

## 1. Project Purpose

`agentic-customersupportflow` is a support-operations demo application built around human-in-the-loop AI workflows.

The product is not a single chatbot. It is an internal operator console for support agents, with:

- a SvelteKit frontend for ticket review and workflow tools
- a FastAPI backend for core AI and Snowflake-backed operations
- Snowflake as the operational data source
- LangGraph-style multi-step ticket analysis
- ChromaDB-backed retrieval for policy grounding
- Whisper transcription for voicemail
- crewAI for a separate Instagram marketing workflow

The system is intentionally designed to surface structured decisions for human review rather than auto-send responses.

## 2. Core Architecture

### Primary stack

- Frontend: SvelteKit + Svelte 4 + Vite
- Backend: FastAPI
- Database: Snowflake
- AI orchestration: LangGraph, LiteLLM, crewAI
- Retrieval: ChromaDB
- Audio transcription: OpenAI Whisper
- File storage: AWS S3 for voicemail uploads

### High-level flow

1. User signs in to the SvelteKit UI.
2. UI loads ticket data, customer data, reasons, and item metadata.
3. The user can inspect returns, manually resolve them, or ask the AI pipeline for a recommendation.
4. For return tickets, the backend runs:
   - triage
   - routing
   - RAG retrieval
   - response draft
   - supervisor validation
5. The result is surfaced to the operator, who still confirms the final action manually.

### Important design principle

The system favors grounded, structured outputs over free-form text. Most nodes and endpoints return JSON objects with explicit schemas and alias mappings.

## 3. Repository Layout

### Frontend

- `src/routes/+page.svelte` - login screen
- `src/routes/+layout.svelte` - app shell, sidebar, auth guard
- `src/routes/dashboard/+page.svelte` - returned items queue and AI/manual resolution flow
- `src/routes/dashboard/create/+page.svelte` - ticket creation wizard
- `src/routes/dashboard/enquiries/+page.svelte` - enquiry queue
- `src/routes/dashboard/instagram-posts/+page.svelte` - crewAI Instagram workflow UI
- `src/lib/stores.js` - app state, ticket loading, AI analyze call, update call
- `src/lib/data.js` - mock return tickets and agent profile data
- `src/lib/enquiry-data.js` - mock enquiry tickets
- `src/lib/snowflake.js` - client-side/server-side Snowflake SDK helper for SvelteKit API routes

### Backend

- `backend/app/main.py` - FastAPI app factory and router registration
- `backend/app/config.py` - environment settings
- `backend/app/db.py` - Snowflake connection and query helper
- `backend/app/models.py` - Pydantic request/response schemas
- `backend/app/routers/*` - API endpoints
- `backend/app/agents/*` - LangGraph pipeline nodes
- `backend/app/rag/*` - policy chunking, scraping, Chroma store, seeding
- `backend/app/services/s3_service.py` - voicemail upload helper

### Data and documentation assets

- `static/database/*.sql` - Snowflake SQL assets and query scripts
- `README.md` - high-level project readme
- `technical-version.md` - architecture explainer already present in the repo
- `conversational-explainer.md` - non-technical summary

## 4. Runtime Topology

There are effectively two server surfaces in this repo:

1. FastAPI backend in `backend/`
2. SvelteKit server routes under `src/routes/api/*`

The FastAPI backend is the main application runtime for the current UI. The SvelteKit API routes mirror some of the same capabilities and use the Snowflake SDK directly. They appear to be a parallel or legacy implementation that still exists in the repo.

When extending the app, do not assume only one backend path exists. Check both before changing data contracts.

## 5. Environment and Configuration

### Backend settings

Defined in `backend/app/config.py` and loaded from `backend/.env`.

Key environment variables:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USERNAME`
- `SNOWFLAKE_PASSWORD`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_ROLE`
- `OPENAI_API_KEY`
- `DALLE_MODEL`
- `DALLE_IMAGE_SIZE`
- `CHROMA_PERSIST_DIR`
- `CHROMA_COLLECTION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `S3_BUCKET_NAME`

### Frontend assumptions

- The SvelteKit UI expects the FastAPI backend at `http://localhost:8000`
- The Snowflake SDK-based SvelteKit routes assume Snowflake env vars are available in the frontend runtime
- Auth state is persisted in `sessionStorage` under `arcella_session`

### Windows note

`backend/app/main.py` contains a Windows UTF-8 guard because LiteLLM imports can fail under the default Windows encoding. This is intentional and should be preserved.

## 6. Frontend Behavior

### Login flow

`src/routes/+page.svelte` is a demo login screen with hardcoded agent credentials. It stores the session in the Svelte store and routes to `/dashboard`.

This is not a real auth system. It is a demo identity gate only.

### App shell

`src/routes/+layout.svelte`:

- imports global styles from `src/app.css`
- blocks access to the dashboard when no session exists
- renders the left sidebar
- exposes nav entries for:
  - Returned Items
  - Enquiry Tickets
  - Create Ticket
  - Instagram Posts Creation

### Returned items dashboard

`src/routes/dashboard/+page.svelte` is the main operator screen.

It supports:

- list and detail view for return tickets
- search and open/closed filtering
- manual resolution selection
- AI analysis via `/api/analyze/ticket`
- closing tickets via `/api/tickets`

This page expects each ticket object to include:

- `id`
- `customer`
- `item`
- `returnAmt`
- `netLoss`
- `returnReason`
- `status`
- `triage`
- `issues`
- `supervisor`

### Ticket creation wizard

`src/routes/dashboard/create/+page.svelte` is a multi-step form that can create either:

- return tickets
- enquiry tickets

It uses:

- customer lookup
- item lookup
- packaging assessment
- financial calculations
- voicemail transcription

For returns, the UI auto-calculates:

- return amount from item price and quantity
- net loss from return amount and packaging factor

### Enquiry queue

`src/routes/dashboard/enquiries/+page.svelte` is a separate operator UI for enquiry-type tickets. It shows the broader support-inquiry taxonomy used by the older/mock data model.

### Instagram workflow UI

`src/routes/dashboard/instagram-posts/+page.svelte` drives the crewAI marketing workflow and supports:

- retrieval toggle
- critique round count
- product selection by item SK or name
- method section content
- campaign caption seed
- live SSE event streaming
- DALL-E image generation

## 7. Shared Client State

### `src/lib/stores.js`

This file is the frontend coordination layer.

It provides:

- `session` - persisted login session
- `tickets` - loaded return tickets
- `ticketsLoading`
- `ticketsError`
- `selectedTicketId`
- `selectedTicket`
- `filters`

It also exposes three important async actions:

- `loadTickets()` - GET `/api/tickets?limit=50`
- `analyzeTicket(ticket)` - POST `/api/analyze/ticket`
- `updateTicketStatus(id, status, resolution)` - PATCH `/api/tickets`

### Important behavior

If live ticket loading fails or returns zero rows, the UI falls back to `MOCK_TICKETS` from `src/lib/data.js`. This means the frontend is deliberately resilient and should never render empty.

## 8. Data Models and Contracts

`backend/app/models.py` is the canonical schema reference for the FastAPI side.

### Ticket analysis request

`AnalyzeTicketRequest` expects:

- `ticket_id`
- `returnReason`
- `returnAmt`
- `netLoss`
- `customer`
- `item`

### Triage response

`TriageResult` contains:

- `action`
- `actionLabel`
- `actionRationale`
- `refundSignal`
- `policyRef`
- `flags`
- `priorityOverride`

### Routing response

`RoutingResult` contains:

- `primaryDepartment`
- `priority`
- `escalationFlags`
- `handlingInstructions`
- `estimatedResolutionTime`

### Response draft

`ResponseDraft` contains:

- `draftResponse`
- `toneApplied`
- `issuesAddressed`
- `ragCitations`
- `requiresEscalation`

### Supervisor report

`SupervisorReport` contains:

- `approved`
- `recommendation`
- `confidenceScore`
- `failures`

### Ticket list response

`TicketListResponse` is the payload the dashboard consumes. It is built from Snowflake rows joined across:

- `STORE_RETURNS`
- `REASON`
- `ITEM`
- `CUSTOMER`
- `DATE_DIM`

## 9. FastAPI Backend

### App entry

`backend/app/main.py`:

- creates the FastAPI app
- installs CORS
- registers all routers
- exposes `/`

Registered routers:

- `health`
- `analyze`
- `rag`
- `tickets`
- `customers`
- `reasons`
- `items`
- `suggest_reason`
- `transcribe`
- `instagram_posts`

### Health

`GET /health` performs a lightweight Snowflake probe using `SELECT 1`.

### Root

`GET /` returns app name, version, docs, and health path.

## 10. Backend Routes

### `GET /health`

Checks service health and Snowflake connectivity.

### `POST /api/analyze/ticket`

Runs the LangGraph pipeline for a single return ticket.

Flow:

1. build initial state from request
2. invoke compiled pipeline
3. validate output models
4. return triage, routing, citations, response, and supervisor result

This is the most important AI endpoint in the project.

### `GET /api/tickets`

Lists tickets from Snowflake. It:

- joins returns with reason, item, customer, and date
- uses a ranked join on `ITEM`
- deduplicates on ticket number
- maps the row into the frontend ticket shape

Important detail:

- `SR_ITEM_SK` in `STORE_RETURNS` is treated as an item rank, not the raw `I_ITEM_SK`
- the code uses `ROW_NUMBER() OVER (ORDER BY I_ITEM_SK)` to reconcile this

### `PATCH /api/tickets`

Updates `SR_STATUS` and optionally `SR_RESOLUTION` for a ticket in Snowflake.

### `POST /api/tickets/create`

Creates a new return ticket in `STORE_RETURNS`.

Notable behavior:

- generates a unique ticket number in a `9910...` range
- resolves customer SK by email when possible
- resolves item rank for `SR_ITEM_SK`
- computes fee as 10 percent of return amount
- stores a structured `SR_RESOLUTION` string with item, packaging, financials, reason, and notes
- falls back to a mock demo ticket if Snowflake write permissions are not available

### `GET /api/customers`

Looks up a customer by email and returns:

- `sk`
- `name`
- `email`
- `preferred`
- `tier`

The tier is derived from the preferred flag and is intentionally simple.

### `GET /api/reasons`

Returns all return reasons from the Snowflake `REASON` table.

### `GET /api/items`

Looks up a single item by `I_ITEM_SK` and also returns its rank `I_RN`.

This endpoint is important because the create-ticket flow needs the ranked value stored in `SR_ITEM_SK`.

### `POST /api/enquiry/transcribe`

Receives a voicemail audio upload, stores it in S3, and transcribes it with Whisper.

Behavior:

- accepts `audio` as multipart upload
- rejects empty or >24 MB files
- uploads to S3 as a non-fatal side effect
- writes the audio to a temp file before sending to Whisper
- returns:
  - transcript
  - S3 key
  - S3 URL
  - size
  - S3 error string if upload failed

### `POST /api/suggest-reason`

Generates a single-sentence internal return reason from complaint and product context.

It uses:

- `gpt-4o-mini` through LiteLLM
- a keyword fallback if the model fails

### `GET /api/rag/stats`

Returns ChromaDB collection stats.

### `POST /api/rag/query`

Semantic search across policy chunks.

### `POST /api/rag/scrape`

Runs the policy scraping pipeline.

### `DELETE /api/rag/domain/{domain}`

Deletes all chunks for a given policy domain.

### `POST /api/instagram-posts/generate`

Synchronous crewAI marketing workflow.

### `POST /api/instagram-posts/generate-stream`

Streaming SSE version of the marketing workflow.

### `POST /api/instagram-posts/generate-image`

Uses DALL-E to generate a visual concept image from the content agent prompt.

## 11. LangGraph Support Pipeline

The return-ticket AI pipeline is implemented under `backend/app/agents/`.

### State contract

`backend/app/agents/state.py` defines `FlowState`, which contains:

- input fields
- triage output
- routing output
- RAG results
- response output
- supervisor report
- error field

### Pipeline order

`backend/app/agents/pipeline.py` wires the graph as:

`triage_node -> routing_node -> rag_node -> response_node -> supervisor_node`

### Triage node

`triage_agent.py`:

- builds a structured ticket brief
- calls LiteLLM with `gpt-4o-mini`
- expects JSON only
- falls back to rule-based logic if the model call fails

This node is responsible for:

- choosing the primary action
- assigning a label and rationale
- emitting refund signals
- adding flags
- optionally setting a priority override

### Routing node

`routing_agent.py`:

- is rule-based, not LLM-based
- maps action to department
- computes priority and SLA
- derives escalation flags
- generates handling instructions

### RAG node

`rag_node.py`:

- maps triage action to a policy issue type
- builds a retrieval query from return reason, category, and product
- queries ChromaDB
- formats citations for downstream use

### Response node

`response_agent.py`:

- takes triage, routing, customer context, item context, and citations
- drafts a customer-facing response using LiteLLM
- must cite only retrieved evidence
- falls back to a template if generation fails

The response is constrained to be:

- grounded
- under 200 words
- personalized by first name
- aligned to customer tier

### Supervisor node

`supervisor_agent.py`:

- checks for issue dropout
- checks for ungrounded claims
- checks escalation handling
- checks tone mismatch
- checks for empty drafts

This is the main anti-silent-failure layer.

### Operational meaning

The pipeline is intentionally conservative. It is better for the supervisor to request revision or escalation than to let an incomplete response pass.

## 12. Retrieval System

### Vector store

`backend/app/rag/store.py` manages a ChromaDB persistent collection named `walmart_policies` by default.

It uses:

- local persistent Chroma storage
- cosine similarity
- domain-based filtering

### Issue-domain mapping

The store maps issue types and triage actions to policy domains such as:

- returns
- shipping
- pricing
- coupons
- warranty
- privacy
- legal
- accessibility
- product_safety
- walmart_plus
- general

### Chunking

`backend/app/rag/chunker.py`:

- splits policies into overlapping chunks
- preserves headers as metadata
- computes token counts
- stores chunk IDs, hashes, section headers, and scrape timestamps

### Scraping

`backend/app/rag/scraper.py`:

- uses Scrapling fetchers
- supports JS-rendered pages via StealthyFetcher when available
- handles HTML and PDF sources
- scrapes Walmart policy pages by domain

### Seed data

`backend/app/rag/seed.py` provides a manual seeding path with prewritten policy summaries.

This is useful when you want the pipeline to work without scraping live pages first.

## 13. S3 and Whisper

`backend/app/services/s3_service.py` is a small upload helper for voicemail audio.

Rules:

- uploads are best-effort
- S3 failures do not block transcription
- keys are date-partitioned
- metadata includes ticket reference and a provenance marker

## 14. Snowflake and SQL

Snowflake is the source of truth for operational ticket data.

The project uses SQL assets under `static/database/` for setup and operational query references.

### Core tables used by the code

- `STORE_RETURNS`
- `REASON`
- `ITEM`
- `CUSTOMER`
- `DATE_DIM`

### Key implementation detail

The returns pipeline depends on a special join strategy:

- `STORE_RETURNS.SR_ITEM_SK` is matched against the ranked position of available items, not directly against raw `ITEM.I_ITEM_SK`

This is why the `ITEM` queries use `ROW_NUMBER() OVER (ORDER BY I_ITEM_SK) AS I_RN`.

### Why this matters

If you change the item lookup or create-ticket logic, you must preserve this rank-based mapping or the dashboard will show the wrong product associations.

## 15. AI Client Rules

If you are another AI client working in this repo, follow these rules:

### Do

- preserve the structured JSON contracts
- keep fallback behavior intact
- respect the human-in-the-loop design
- use the existing env var names
- maintain the item-rank mapping in Snowflake
- keep response outputs short and grounded
- validate user-facing claims against citations when possible

### Do not

- invent policy details
- remove fallback paths without replacing them
- assume the frontend only talks to one backend
- break the alias mappings between backend models and frontend payloads
- auto-send customer responses
- remove the supervisor checks
- change the ranked item join without checking the ticket model end to end

## 16. Practical Extension Notes

### If you add a new AI flow

- define a Pydantic model first
- define a state contract or request schema
- decide whether the node should be LLM-based or rule-based
- add explicit validation before returning data to the UI

### If you change ticket schema

- update:
  - `backend/app/models.py`
  - `src/lib/stores.js`
  - `src/routes/dashboard/+page.svelte`
  - any SvelteKit API mirrors if they still matter

### If you change Snowflake queries

- check both the FastAPI route and the SvelteKit route version
- keep the rank join logic consistent for item resolution
- verify create and update paths still work

### If you change the RAG layer

- update the domain mapping in `backend/app/rag/store.py`
- ensure the supervisor still sees citations in the expected shape
- preserve source metadata fields:
  - `source_doc`
  - `source_section`
  - `source_url`
  - `confidence`

## 17. Summary

This repository is a support-ops system with a structured multi-agent backend, Snowflake-backed operational data, policy retrieval, transcription, and a marketing workflow. The safest mental model is:

- SvelteKit is the operator console
- FastAPI is the main service layer
- Snowflake is the operational truth
- LangGraph handles support triage
- ChromaDB grounds policy claims
- crewAI handles the marketing content demo

If you are extending the system, keep the contracts explicit and the fallback behavior intact.
