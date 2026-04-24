# agentic-customersupportflow

A SvelteKit + FastAPI support-ops demo for handling customer returns, enquiries, analytics, and AI-assisted marketing workflows.

## What It Does

- Customer support dashboard with queue, ticket creation, and enquiry review flows
- Enquiry analysis that classifies messages, drafts replies, and validates against Snowflake procedure output
- Return workflow with AI-assisted triage and response drafting
- Instagram post generation workflow with crewAI, Snowflake lookup, and OpenAI image generation
- Analytics dashboard backed by backend data

## Tech Stack

- Frontend: SvelteKit
- Backend: FastAPI
- Database: Snowflake
- AI/LLM: OpenAI via LiteLLM
- Agent workflows: LangGraph, crewAI

## Project Structure

- `src/` - SvelteKit frontend
- `backend/` - FastAPI backend
- `static/database/` - Snowflake SQL schema and procedure files
- `README.md` - project overview and setup

## Requirements

- Node.js 18+
- Python 3.11+
- Snowflake credentials
- OpenAI API key

## Setup

### 1. Install frontend dependencies

```bash
npm install
```

### 2. Install backend dependencies

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Edit `backend/.env` with your local values.

Required variables:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USERNAME`
- `SNOWFLAKE_PASSWORD`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_ROLE`
- `OPENAI_API_KEY`

Optional variables:

- `APP_ENV`
- `CORS_ORIGINS`
- `IMAGE_MODEL` - defaults to `gpt-image-2`
- `IMAGE_SIZE`

## Run Locally

### Backend

From `backend/`:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` by default.

### Frontend

From the project root:

```bash
npm run dev
```

The app will usually run at `http://localhost:5173`.

## Main Workflows

### Dashboard

Shows summary analytics and overall support health.

### Create Ticket

Handles return-ticket creation and related customer lookup workflows.

### Customer Enquiries

This is the main enquiry workflow:

1. Paste an email, chat transcript, or voicemail transcript
2. Click `Analyze Enquiry`
3. Backend classifies the enquiry category and subcategory
4. Backend calls the matching Snowflake procedure
5. The returned Snowflake data is treated as the source of truth
6. The UI shows the draft response, validation questions, and source rows for review

### Instagram Posts Creation

Uses crewAI + Snowflake context to draft social content and generate a visual suggestion with OpenAI image generation.

## API Overview

Key endpoints used by the UI:

- `POST /api/enquiry/analyze`
- `POST /api/enquiry/create`
- `POST /api/enquiry/transcribe`
- `POST /api/instagram-posts/generate`
- `POST /api/instagram-posts/generate-stream`
- `POST /api/instagram-posts/generate-image`
- `GET /api/analytics/dashboard`
- `GET /api/customers`
- `GET /api/items`
- `POST /api/tickets/create`

## Snowflake Assets

The `static/database/` folder contains the SQL used to define the sample data model, including enquiry procedures and ticket schemas.

Important enquiry procedures:

- `ORDER_DELIVERY_PROCEDURE`
- `RETURNS_REFUNDS_PROCEDURE`
- `BILLING_PAYMENT_PROCEDURE`
- `ACCOUNT_MANAGEMENT_PROCEDURE`
- `GENERAL_ENQUIRY_PROCEDURE`

## Notes

- The voicemail flow now transcribes audio directly with OpenAI Whisper and does not depend on AWS or S3.
- Image generation now uses OpenAI's `gpt-image-2` model name in config and docs.
- The enquiry workflow is designed so Snowflake procedure output is the validation source of truth.

## License

See `LICENSE` for project licensing details.
