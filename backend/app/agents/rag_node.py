# app/agents/rag_node.py
"""
RAG Retrieval Node -- LangGraph node that queries ChromaDB.

Reads the triage output from state, maps the action/issue_type to
policy domains, and writes retrieved policy citations into
state["rag_results"] for the response agent to use.

No LLM call here -- just a vector DB query (~5ms).
"""
from __future__ import annotations

import logging
from app.agents.state import FlowState
from app.rag.store import get_store

logger = logging.getLogger("agents.rag_node")


def rag_retrieval_node(state: FlowState) -> FlowState:
    """
    LangGraph node: query ChromaDB for policy evidence.

    Reads:
      - state["triage"]["action"]  (from triage_agent)
      - state["return_reason"]     (original ticket context)
      - state["item_ctx"]          (category, product name)

    Writes:
      - state["rag_results"]  list of citation dicts
    """
    try:
        store = get_store()
        triage = state.get("triage", {})

        # Determine issue type from triage action
        action = triage.get("action", "")
        issue_type = _action_to_issue_type(action)

        # Build a rich query from the ticket context
        reason = state.get("return_reason", "")
        item = state.get("item_ctx", {})
        category = item.get("category", "")
        product = item.get("name", "")
        query_text = f"{reason} {category} {product}".strip()

        if not query_text:
            query_text = action.replace("_", " ")

        logger.info(
            "RAG query: issue_type=%s, query='%s'",
            issue_type, query_text[:80],
        )

        # Query ChromaDB
        results = store.query_by_issue_type(issue_type, query_text, n_results=5)

        # Format for downstream agents
        rag_results = [
            {
                "claim":          r["content"][:300],
                "source_doc":     r["metadata"]["policy_name"],
                "source_section": r["metadata"]["section_header"],
                "source_url":     r["metadata"]["source_url"],
                "confidence":     r["similarity"],
            }
            for r in results
        ]

        logger.info("RAG retrieved %d citations (top: %.3f)",
                     len(rag_results),
                     rag_results[0]["confidence"] if rag_results else 0)

        return {**state, "rag_results": rag_results, "error": None}

    except Exception as exc:
        logger.error("RAG retrieval failed: %s", exc)
        # Non-fatal: downstream agents can still work without citations
        return {**state, "rag_results": [], "error": f"RAG failed: {exc}"}


def _action_to_issue_type(action: str) -> str:
    """
    Map triage action strings to issue types recognized by the store.
    The store's ISSUE_DOMAIN_MAP handles both action strings and
    generic issue types, so we just pass through.
    """
    if not action:
        return "general_inquiry"
    return action
