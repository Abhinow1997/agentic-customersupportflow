# app/routers/health.py
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timezone

from app.config import get_settings
from app.db import run_query

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


# ── Response schemas ────────────────────────────────────────────────────────

class ServiceStatus(BaseModel):
    status: str          # "ok" | "degraded" | "error"
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str          # overall: "ok" | "degraded" | "error"
    app: str
    version: str
    environment: str
    timestamp: str
    services: dict[str, ServiceStatus]


# ── Endpoint ────────────────────────────────────────────────────────────────

@router.get("", response_model=HealthResponse, summary="Health check")
async def health_check():
    """
    Returns the health of the API and its upstream dependencies.

    - **status**: overall roll-up (`ok` if all services are healthy)
    - **services.snowflake**: result of a lightweight `SELECT 1` probe
    """
    snowflake_status = _probe_snowflake()

    overall = (
        "ok"
        if snowflake_status.status == "ok"
        else "degraded"
    )

    return HealthResponse(
        status=overall,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={"snowflake": snowflake_status},
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _probe_snowflake() -> ServiceStatus:
    """Ping Snowflake with SELECT 1 and measure round-trip time."""
    start = datetime.now(timezone.utc)
    try:
        run_query("SELECT 1 AS ping")
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return ServiceStatus(status="ok", latency_ms=round(elapsed, 2))
    except Exception as exc:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return ServiceStatus(
            status="error",
            latency_ms=round(elapsed, 2),
            detail=str(exc),
        )
