# app/rag/store.py
"""
ChromaDB vector store for Walmart policy chunks.

Uses ChromaDB's built-in sentence-transformer embeddings
(all-MiniLM-L6-v2) -- no OpenAI API key needed for embeddings.

Singleton pattern: the collection is created once at import time
and reused across all requests (same as pipeline.py does with the
LangGraph graph).
"""
from __future__ import annotations

import logging
from functools import lru_cache

import chromadb

from app.config import get_settings

logger = logging.getLogger("rag.store")
settings = get_settings()

# Configurable via .env (defaults work out of the box)
CHROMA_PATH = getattr(settings, "CHROMA_PERSIST_DIR", "./chroma_walmart_policies")
COLLECTION_NAME = getattr(settings, "CHROMA_COLLECTION", "walmart_policies")


# ── Issue type -> policy domain mapping ───────────────────────────────────
# The triage agent outputs an `action` string. The RAG node maps that
# action (or an explicit issue_type) to the policy domains that should
# be searched in ChromaDB.

ISSUE_DOMAIN_MAP: dict[str, list[str] | None] = {
    # Triage actions (from triage_agent.py)
    "refund":                ["returns"],
    "refund_or_reship":      ["returns", "shipping"],
    "replacement":           ["returns", "warranty"],
    "replacement_escalate":  ["returns", "product_safety", "warranty"],
    "exchange_first":        ["returns"],
    "retention_offer":       ["returns", "walmart_plus"],
    "escalate_quality":      ["product_safety"],

    # Generic issue types (from enquiry-data / triage taxonomy)
    "return_request":        ["returns"],
    "refund_complaint":      ["returns"],
    "billing_complaint":     ["pricing", "coupons", "legal"],
    "billing_dispute":       ["pricing", "legal"],
    "payment_issue":         ["legal", "walmart_plus"],
    "product_quality":       ["product_safety", "returns"],
    "product_safety":        ["product_safety"],
    "account_mgmt":          ["privacy", "walmart_plus"],
    "warranty_claim":        ["warranty"],
    "pharmacy":              ["pharmacy"],
    "coupon_issue":          ["coupons"],
    "shipping_issue":        ["shipping"],
    "order_status":          ["shipping"],
    "pickup_issue":          ["shipping"],
    "technical_issue":       ["accessibility", "legal"],
    "subscription_cancellation": ["walmart_plus"],
    "address_change":        ["shipping"],
    "product_question":      ["product_safety"],
    "bulk_order_inquiry":    ["shipping", "pricing"],
    "vendor_onboarding":     ["general"],
    "payment_dispute":       ["pricing", "legal"],
    "policy_inquiry":        None,   # search ALL domains
    "churn_signal":          ["walmart_plus", "pricing"],
    "general_inquiry":       None,   # search ALL
}


class PolicyVectorStore:
    """
    Thin wrapper around a ChromaDB collection.

    All methods are synchronous -- ChromaDB is local and fast (~5ms).
    The LangGraph node calls these inside sync functions which LangGraph
    runs in a thread pool, so no async needed.
    """

    def __init__(self, persist_dir: str = CHROMA_PATH,
                 collection_name: str = COLLECTION_NAME):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "description": "Walmart customer policy documents for RAG",
                "hnsw:space": "cosine",
            }
        )
        logger.info(
            "ChromaDB collection '%s' ready (%d chunks)",
            collection_name, self.collection.count()
        )

    # ── Write ─────────────────────────────────────────────────────────────

    def upsert_chunks(self, chunks: list[dict]) -> int:
        """
        Add or update chunks. ChromaDB upsert handles dedup by ID.
        Returns the number of chunks upserted.
        """
        if not chunks:
            return 0

        ids = [c["chunk_id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [{
            "source_url":     c["source_url"],
            "domain":         c["domain"],
            "policy_name":    c["policy_name"],
            "priority":       c["priority"],
            "chunk_index":    c["chunk_index"],
            "total_chunks":   c["total_chunks"],
            "token_count":    c["token_count"],
            "content_hash":   c["content_hash"],
            "section_header": c["section_header"],
            "scraped_at":     c["scraped_at"],
        } for c in chunks]

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    # ── Read ──────────────────────────────────────────────────────────────

    def query_by_text(self, query: str, n_results: int = 5,
                      domain_filter: str | None = None) -> list[dict]:
        """Semantic search across policy chunks."""
        where_filter = {"domain": domain_filter} if domain_filter else None

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if not results["ids"] or not results["ids"][0]:
            return output

        for i in range(len(results["ids"][0])):
            output.append({
                "chunk_id":   results["ids"][0][i],
                "content":    results["documents"][0][i],
                "metadata":   results["metadatas"][0][i],
                "distance":   results["distances"][0][i],
                "similarity": round(1 - results["distances"][0][i], 4),
            })
        return output

    def query_by_issue_type(self, issue_type: str, query: str,
                            n_results: int = 5) -> list[dict]:
        """
        RAG retrieval mapped from triage action / issue_type.

        This is the primary method the LangGraph rag_node calls.
        """
        domains = ISSUE_DOMAIN_MAP.get(issue_type)

        # None = search all domains (policy_inquiry, general)
        if domains is None:
            return self.query_by_text(query, n_results)

        if len(domains) == 1:
            return self.query_by_text(query, n_results, domain_filter=domains[0])

        # Multiple domains: query each, merge by similarity
        all_results = []
        per_domain = max(3, n_results // len(domains))
        for domain in domains:
            results = self.query_by_text(query, per_domain, domain_filter=domain)
            all_results.extend(results)

        # Sort by similarity desc, dedupe, trim
        all_results.sort(key=lambda x: x["similarity"], reverse=True)
        seen = set()
        deduped = []
        for r in all_results:
            if r["chunk_id"] not in seen:
                seen.add(r["chunk_id"])
                deduped.append(r)
        return deduped[:n_results]

    # ── Admin ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Collection statistics for /api/rag/stats."""
        count = self.collection.count()
        if count == 0:
            return {"total_chunks": 0, "domains": {}}

        all_data = self.collection.get(include=["metadatas"])
        domain_counts: dict[str, int] = {}
        for meta in all_data["metadatas"]:
            d = meta.get("domain", "unknown")
            domain_counts[d] = domain_counts.get(d, 0) + 1

        return {
            "total_chunks": count,
            "domains": dict(sorted(domain_counts.items())),
        }

    def delete_domain(self, domain: str) -> int:
        """Remove all chunks for a domain (for re-scraping)."""
        before = self.collection.count()
        self.collection.delete(where={"domain": domain})
        after = self.collection.count()
        return before - after


# ── Module-level singleton ────────────────────────────────────────────────
# Compiled once on first import, reused across all requests.

@lru_cache(maxsize=1)
def get_store() -> PolicyVectorStore:
    return PolicyVectorStore()
