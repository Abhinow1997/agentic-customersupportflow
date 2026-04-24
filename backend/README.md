# FastAPI Backend

Python FastAPI backend for the Arcella Customer Operations Platform.  
Runs alongside the SvelteKit frontend and connects to Snowflake.

---

## Setup

```bash
cd backend

# 1. Create & activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the dev server
uvicorn app.main:app --reload --port 8000
```

The `.env` file in this directory is already pre-filled with the Snowflake credentials.

---

## Deployment Links

This backend is designed to run as a separate FastAPI service alongside the SvelteKit frontend.

Replace the placeholders below with the live deployment URLs for your environment:

- Backend API: `https://<your-backend-deployment>`
- Backend docs: `https://<your-backend-deployment>/docs`
- Backend health check: `https://<your-backend-deployment>/health`
- Frontend app: `https://<your-frontend-deployment>.vercel.app`

If the frontend is deployed separately, make sure its `PUBLIC_FASTAPI_URL` points at the live backend instead of `http://localhost:8000`.

---

## Endpoints

| Method | Path      | Description                          |
|--------|-----------|--------------------------------------|
| GET    | `/`       | API root — version info + links      |
| GET    | `/health` | Health check + Snowflake probe       |
| GET    | `/docs`   | Swagger UI (auto-generated)          |
| GET    | `/redoc`  | ReDoc UI (auto-generated)            |

### `GET /health` — example response

```json
{
  "status": "ok",
  "app": "Arcella Support API",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2025-03-02T10:00:00+00:00",
  "services": {
    "snowflake": {
      "status": "ok",
      "latency_ms": 312.4,
      "detail": null
    }
  }
}
```

---

## Project structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          ← FastAPI app + middleware + router registration
│   ├── config.py        ← Pydantic settings (reads .env)
│   ├── db.py            ← Snowflake connection + query helper
│   └── routers/
│       ├── __init__.py
│       └── health.py    ← GET /health
├── .env                 ← Snowflake credentials (git-ignored in prod)
├── requirements.txt
└── README.md
```

---

## Coming next

- `GET /api/tickets` — fetch + triage returns from Snowflake  
- `PATCH /api/tickets` — update ticket status + resolution  
- `GET /api/reasons` — return reason lookup  
- `/api/agent/*` — Claude-powered triage / draft / supervisor endpoints
