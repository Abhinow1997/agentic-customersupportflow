# app/routers/rag.py
"""
RAG admin and query endpoints.

  GET  /api/rag/stats              -- ChromaDB collection stats
  POST /api/rag/query              -- test semantic search
  POST /api/rag/scrape             -- trigger policy re-scrape
  DELETE /api/rag/domain/{domain}  -- delete a domain's chunks
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag.store import get_store

logger = logging.getLogger("routers.rag")

router = APIRouter(prefix="/api/rag", tags=["rag"])


# ── Stats ─────────────────────────────────────────────────────────────────

@router.get("/stats", summary="ChromaDB collection statistics")
async def rag_stats():
    store = get_store()
    return store.get_stats()


# ── Query ─────────────────────────────────────────────────────────────────

class RagQueryRequest(BaseModel):
    query: str
    issue_type: str | None = None
    domain: str | None = None
    n_results: int = 5


@router.post("/query", summary="Semantic search across policy chunks")
async def rag_query(req: RagQueryRequest):
    store = get_store()

    if req.issue_type:
        results = store.query_by_issue_type(req.issue_type, req.query, req.n_results)
    elif req.domain:
        results = store.query_by_text(req.query, req.n_results, domain_filter=req.domain)
    else:
        results = store.query_by_text(req.query, req.n_results)

    return {
        "query": req.query,
        "issue_type": req.issue_type,
        "domain": req.domain,
        "results": results,
        "count": len(results),
    }


# ── Scrape trigger ────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    domain: str | None = None
    delay: float = 2.0


@router.post("/scrape", summary="Trigger policy scrape pipeline")
async def rag_scrape(req: ScrapeRequest):
    """
    Runs the Scrapling scraper to fetch Walmart policy pages,
    chunk them, and upsert into ChromaDB.

    This is a blocking call -- for production, run as a background task.
    """
    try:
        from app.rag.scraper import run_scrape_pipeline
        stats = run_scrape_pipeline(domain_filter=req.domain, delay=req.delay)
        return {"status": "ok", "stats": stats}
    except Exception as exc:
        logger.error("Scrape failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Delete domain ─────────────────────────────────────────────────────────

@router.delete("/domain/{domain}", summary="Delete all chunks for a domain")
async def rag_delete_domain(domain: str):
    store = get_store()
    deleted = store.delete_domain(domain)
    return {"status": "ok", "domain": domain, "deleted": deleted}
