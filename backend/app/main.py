# app/main.py
import sys

# ── Windows UTF-8 guard ───────────────────────────────────────────────────
# litellm opens its model-pricing JSON at import time. On Windows the default
# locale encoding (cp1252) cannot decode the file, causing a UnicodeDecodeError.
# Setting UTF-8 mode before any litellm import prevents the crash.
if sys.platform == "win32":
    import os
    os.environ.setdefault("PYTHONUTF8", "1")
    # Also force the std streams to utf-8 so log output doesn't break
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health, analyze, rag, tickets, customers, reasons, items, suggest_reason

settings = get_settings()

# ── App factory ─────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend API for the Arcella Customer Operations Platform. "
        "Serves ticket data from Snowflake and will host the multi-agent "
        "support pipeline (triage → routing → response → supervisor)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(rag.router)
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(reasons.router)
app.include_router(items.router)
app.include_router(suggest_reason.router)

# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["root"], summary="API root")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
