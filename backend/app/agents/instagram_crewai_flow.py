"""
CrewAI-based Instagram marketing workflow with explicit orchestration.

Flow:
User Input -> Controller Agent -> Reviewer Agent (Snowflake, optional)
-> Scraper Tool + Scraper Analyst (optional)
-> Summary Validator Agent -> Content Agent -> Critique Loop
-> Formatter Agent -> Final Output

Includes:
- Standardized backend logging envelope for agent communication/events
- Shared memory context across stages
- Crew memory enabled for each agent invocation
- event_callback: optional callable(dict) — called with streaming events per stage
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from crewai import Agent, Crew, Process, Task

from app.config import get_settings
from app.db import run_query

logger = logging.getLogger("agents.instagram_crewai")
logger.setLevel(logging.INFO)


class InstagramFlowError(Exception):
    """Base error for the Instagram crew flow."""


class AlignmentError(InstagramFlowError):
    """Raised when merged summary does not align with user expectations."""


@dataclass
class InstagramFlowInput:
    retrieval_enabled: bool
    critique_rounds: int
    product_item_sk: int | None
    product_name: str | None
    method_section_content: str
    product_marketing_campaign_caption: str


def run_instagram_crewai_flow(
    payload: InstagramFlowInput,
    event_callback: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    _ensure_crewai_environment()

    run_id = uuid4().hex[:12]
    memory_context: list[str] = []
    stage_outputs: list[dict[str, Any]] = []
    warnings: list[str] = []

    # ── Streaming helper ────────────────────────────────────────────────────
    def emit(event_type: str, **kwargs) -> None:
        if event_callback is None:
            return
        try:
            event_callback({"type": event_type, **kwargs})
        except Exception:
            pass

    # ── Flow start ──────────────────────────────────────────────────────────
    _log_event(run_id, "FLOW_START", {"product_ref": _product_reference(payload)})
    _remember(memory_context, "User Input", _payload_summary(payload))
    _log_comm(
        run_id,
        "User Input",
        "Controller Agent",
        "start_workflow",
        {"retrieval_enabled": payload.retrieval_enabled, "critique_rounds": payload.critique_rounds},
    )

    # ── Controller ──────────────────────────────────────────────────────────
    emit("agent_start", stage="controller", agent="Controller Agent")
    controller_plan = _controller_delegate(payload, run_id, memory_context)
    stage_outputs.append(
        {"stage": "controller", "agent": "Controller Agent", "output": controller_plan}
    )
    emit("agent_complete", stage="controller", agent="Controller Agent", output=controller_plan)
    _remember(memory_context, "Controller Plan", controller_plan)

    reviewer_output: dict[str, Any] = {
        "source_truth_summary": "Reviewer skipped.",
        "selected_product": None,
        "selection_reason": "Retrieval disabled or not delegated.",
    }
    scraped_output: dict[str, Any] = {
        "scraped_summary": "Scraper skipped.",
        "web_claims": [],
        "product_angle": "",
    }

    # ── Reviewer ────────────────────────────────────────────────────────────
    if controller_plan["use_reviewer"]:
        _log_comm(
            run_id,
            "Controller Agent",
            "Reviewer Agent",
            "delegate_source_truth",
            {"product_ref": _product_reference(payload)},
        )

        emit("agent_start", stage="reviewer_query", agent="Reviewer Agent")
        rows = _fetch_product_rows(payload, run_id)
        stage_outputs.append(
            {
                "stage": "reviewer_query",
                "agent": "Reviewer Agent",
                "output": {"rows_found": len(rows)},
            }
        )
        emit(
            "agent_complete",
            stage="reviewer_query",
            agent="Reviewer Agent",
            output={"rows_found": len(rows)},
        )

        emit("agent_start", stage="reviewer", agent="Reviewer Agent")
        reviewer_output = _reviewer_source_truth(payload, rows, run_id, memory_context)
        stage_outputs.append(
            {"stage": "reviewer", "agent": "Reviewer Agent", "output": reviewer_output}
        )
        emit("agent_complete", stage="reviewer", agent="Reviewer Agent", output=reviewer_output)
        _remember(memory_context, "Reviewer Output", reviewer_output)

        selected = reviewer_output.get("selected_product") or {}
        product_url = selected.get("i_product_url")

        # ── Scraper ─────────────────────────────────────────────────────────
        if controller_plan["use_scraper"] and product_url:
            _log_comm(
                run_id,
                "Controller Agent",
                "Scraper Agent",
                "delegate_scrape",
                {"product_url": str(product_url)},
            )
            emit("agent_start", stage="scraper", agent="Scraper Agent")
            try:
                scraped_data = _scrape_walmart_product_data(str(product_url), run_id)
                scraped_output = _scraper_analysis(payload, scraped_data, run_id, memory_context)
                stage_outputs.append(
                    {
                        "stage": "scraper",
                        "agent": "Scraper Agent",
                        "output": {"scraped_data": scraped_data, "analysis": scraped_output},
                    }
                )
            except Exception as exc:
                scraped_output = {
                    "scraped_summary": f"Scraper failed: {exc}",
                    "web_claims": [],
                    "product_angle": "",
                }
                _log_event(run_id, "SCRAPER_ERROR", {"error": str(exc)})
                warning_msg = f"Scraper step failed: {exc}"
                warnings.append(warning_msg)
                emit("flow_warning", message=warning_msg)
                stage_outputs.append(
                    {
                        "stage": "scraper",
                        "agent": "Scraper Agent",
                        "output": scraped_output,
                    }
                )
            emit("agent_complete", stage="scraper", agent="Scraper Agent", output=scraped_output)
            _remember(memory_context, "Scraper Output", scraped_output)

    # ── Summary Validator ───────────────────────────────────────────────────
    _log_comm(
        run_id,
        "Controller Agent",
        "Summary Validator Agent",
        "merge_and_validate",
        {"has_reviewer": controller_plan["use_reviewer"], "has_scraper": controller_plan["use_scraper"]},
    )
    emit("agent_start", stage="summary_validation", agent="Summary Validator Agent")
    validation_output = _summary_validation(
        payload=payload,
        controller_plan=controller_plan,
        reviewer_output=reviewer_output,
        scraped_output=scraped_output,
        run_id=run_id,
        memory_context=memory_context,
    )
    stage_outputs.append(
        {
            "stage": "summary_validation",
            "agent": "Summary Validator Agent",
            "output": validation_output,
        }
    )
    emit(
        "agent_complete",
        stage="summary_validation",
        agent="Summary Validator Agent",
        output=validation_output,
    )
    _remember(memory_context, "Validation Output", validation_output)

    # ── Realignment pass (if needed) ────────────────────────────────────────
    if not bool(validation_output.get("aligned", False)):
        notes = validation_output.get("alignment_notes", "Unknown alignment mismatch.")
        _log_event(run_id, "FLOW_ALIGNMENT_NEEDS_REALIGNMENT", {"alignment_notes": notes})
        warning_msg = f"Summary required realignment: {notes}"
        warnings.append(warning_msg)
        emit("flow_warning", message=warning_msg)
        _log_comm(
            run_id,
            "Controller Agent",
            "Summary Validator Agent",
            "realign_summary",
            {"reason": notes},
        )
        emit("agent_start", stage="summary_realign", agent="Summary Validator Agent")
        validation_output = _realign_summary(
            payload=payload,
            validation_output=validation_output,
            run_id=run_id,
            memory_context=memory_context,
        )
        stage_outputs.append(
            {
                "stage": "summary_realign",
                "agent": "Summary Validator Agent",
                "output": validation_output,
            }
        )
        emit(
            "agent_complete",
            stage="summary_realign",
            agent="Summary Validator Agent",
            output=validation_output,
        )
        _remember(memory_context, "Realigned Validation Output", validation_output)

    # ── Content generation ──────────────────────────────────────────────────
    _log_comm(run_id, "Controller Agent", "Content Agent", "generate_content", {})
    emit("agent_start", stage="content_generation", agent="Content Agent")
    content_output = _generate_content(payload, validation_output, run_id, memory_context)
    stage_outputs.append(
        {"stage": "content_generation", "agent": "Content Agent", "output": content_output}
    )
    emit("agent_complete", stage="content_generation", agent="Content Agent", output=content_output)
    _remember(memory_context, "Content Output", content_output)

    # ── Critique loop ───────────────────────────────────────────────────────
    iteration_notes: list[str] = []
    critique_rounds = int(controller_plan.get("critique_rounds", payload.critique_rounds))
    critique_rounds = max(0, min(5, critique_rounds))

    for round_idx in range(1, critique_rounds + 1):
        _log_comm(
            run_id,
            "Controller Agent",
            "Critique Agent",
            "critique_round",
            {"round": round_idx},
        )
        emit("agent_start", stage=f"critique_round_{round_idx}", agent="Critique Agent")
        critique_output = _critique_content(payload, content_output, round_idx, run_id, memory_context)
        stage_outputs.append(
            {
                "stage": f"critique_round_{round_idx}",
                "agent": "Critique Agent",
                "output": critique_output,
            }
        )
        emit(
            "agent_complete",
            stage=f"critique_round_{round_idx}",
            agent="Critique Agent",
            output=critique_output,
        )
        _remember(memory_context, f"Critique Round {round_idx}", critique_output)
        iteration_notes.append(
            f"Round {round_idx}: {str(critique_output.get('round_feedback', 'Content refined.'))}"
        )

        _log_comm(
            run_id,
            "Critique Agent",
            "Content Agent",
            "revise_content",
            {"round": round_idx},
        )
        emit(
            "agent_start",
            stage=f"content_revision_round_{round_idx}",
            agent="Content Agent",
        )
        content_output = _revise_content(
            payload, content_output, critique_output, round_idx, run_id, memory_context
        )
        stage_outputs.append(
            {
                "stage": f"content_revision_round_{round_idx}",
                "agent": "Content Agent",
                "output": content_output,
            }
        )
        emit(
            "agent_complete",
            stage=f"content_revision_round_{round_idx}",
            agent="Content Agent",
            output=content_output,
        )
        _remember(memory_context, f"Revised Content Round {round_idx}", content_output)

    # ── Formatter ───────────────────────────────────────────────────────────
    _log_comm(run_id, "Controller Agent", "Formatter Agent", "format_final_output", {})
    emit("agent_start", stage="formatter", agent="Formatter Agent")
    formatted_output = _format_final_output(
        payload=payload,
        validation_output=validation_output,
        content_output=content_output,
        iteration_notes=iteration_notes,
        run_id=run_id,
        memory_context=memory_context,
    )
    stage_outputs.append(
        {"stage": "formatter", "agent": "Formatter Agent", "output": formatted_output}
    )
    emit("agent_complete", stage="formatter", agent="Formatter Agent", output=formatted_output)

    posts = _normalize_posts(formatted_output.get("posts"))
    if not posts:
        posts = _default_posts(content_output, payload)
        _log_event(run_id, "FORMATTER_POSTS_EMPTY_FALLBACK", {"fallback_posts": len(posts)})

    result = {
        "runId": run_id,
        "workflow": "crewai_instagram_posts_supervisor_v2",
        "usedCrewAI": True,
        "strategySummary": formatted_output.get(
            "strategySummary",
            validation_output.get("merged_summary", "Campaign strategy generated."),
        ),
        "iterationNotes": formatted_output.get("iterationNotes", iteration_notes),
        "posts": posts,
        "controllerPlan": controller_plan,
        "sourceTruth": reviewer_output.get("source_truth_summary", ""),
        "scrapedSummary": scraped_output.get("scraped_summary", ""),
        "visualizerPrompt": content_output.get("visual_prompt", ""),
        "marketingDescription": content_output.get("marketing_description", ""),
        "validationResult": validation_output,
        "agentOutputs": stage_outputs,
        "warnings": warnings,
    }
    _log_event(run_id, "FLOW_COMPLETE", {"post_count": len(posts)})
    return result


# ── Agent implementations (unchanged) ────────────────────────────────────────

def _ensure_crewai_environment() -> None:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise InstagramFlowError(
            "OPENAI_API_KEY is not configured. crewAI workflow cannot run without it."
        )
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY


def _controller_delegate(
    payload: InstagramFlowInput, run_id: str, memory_context: list[str]
) -> dict[str, Any]:
    input_blob = {
        "retrieval_enabled": payload.retrieval_enabled,
        "critique_rounds": payload.critique_rounds,
        "product_item_sk": payload.product_item_sk,
        "product_name": payload.product_name,
        "method_section_content": payload.method_section_content,
        "product_marketing_campaign_caption": payload.product_marketing_campaign_caption,
    }

    response = _run_agent_json(
        role="Controller Agent",
        goal=(
            "Act as workflow supervisor and decide task delegation for reviewer, scraper, "
            "content generation, and critique loop."
        ),
        backstory=(
            "You orchestrate a marketing content pipeline and decide what steps are required "
            "based on user constraints and data availability."
        ),
        description=(
            "Given the user input JSON below, decide delegation.\n"
            "Rules:\n"
            "- If retrieval_enabled is true, use_reviewer must be true.\n"
            "- use_scraper should be true when reviewer likely provides product URL.\n"
            "- critique_rounds must be 0..5.\n"
            "Return JSON with keys: use_reviewer, use_scraper, critique_rounds, "
            "decision_rationale, user_expectations_summary.\n\n"
            f"User Input:\n{json.dumps(input_blob, indent=2)}"
        ),
        expected_output=(
            "Valid JSON object with use_reviewer (bool), use_scraper (bool), "
            "critique_rounds (int), decision_rationale (string), user_expectations_summary (string)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    use_reviewer = bool(response.get("use_reviewer")) and payload.retrieval_enabled
    use_scraper = bool(response.get("use_scraper")) and use_reviewer
    critique_rounds = int(response.get("critique_rounds", payload.critique_rounds))
    critique_rounds = max(0, min(5, critique_rounds))

    plan = {
        "use_reviewer": use_reviewer,
        "use_scraper": use_scraper,
        "critique_rounds": critique_rounds,
        "decision_rationale": str(response.get("decision_rationale", "")),
        "user_expectations_summary": str(response.get("user_expectations_summary", "")),
    }
    _log_event(run_id, "CONTROLLER_PLAN", plan)
    return plan


def _fetch_product_rows(payload: InstagramFlowInput, run_id: str) -> list[dict]:
    sql = """
    SELECT
        i_item_sk,
        i_item_id,
        i_product_name,
        i_category,
        i_class,
        i_category_full,
        i_brand,
        i_current_price,
        i_list_price,
        i_list_price - i_current_price          AS markdown_amt,
        ROUND(100.0 * (i_list_price - i_current_price)
              / NULLIF(i_list_price, 0), 2)      AS markdown_pct,
        i_available,
        i_package_size,
        i_gtin,
        i_item_number,
        i_product_url,
        i_crawl_timestamp
    FROM SYNTHETIC_COMPANYDB.COMPANY.ITEM
    WHERE (%s IS NOT NULL AND i_item_sk = %s)
       OR (%s IS NOT NULL AND LOWER(i_product_name) = LOWER(%s))
    """
    params = (
        payload.product_item_sk,
        payload.product_item_sk,
        payload.product_name,
        payload.product_name,
    )
    rows = run_query(sql, params)
    _log_event(
        run_id,
        "SNOWFLAKE_QUERY_COMPLETE",
        {"rows": len(rows), "product_ref": _product_reference(payload)},
    )
    return rows


def _reviewer_source_truth(
    payload: InstagramFlowInput, rows: list[dict], run_id: str, memory_context: list[str]
) -> dict[str, Any]:
    safe_rows = rows[:10]
    response = _run_agent_json(
        role="Reviewer Agent",
        goal=(
            "Produce a source-of-truth product summary from Snowflake ITEM data and select "
            "the best matching product record for downstream use."
        ),
        backstory=(
            "You validate product facts from the data warehouse and prevent unsupported claims "
            "in marketing content."
        ),
        description=(
            "Use the query result rows below as source truth.\n"
            "Return JSON with keys: source_truth_summary, selected_product, selection_reason.\n"
            "- selected_product must be one row object or null if no valid row.\n"
            "- source_truth_summary must mention pricing, brand/category context, and availability.\n\n"
            f"Requested item_sk: {payload.product_item_sk}\n"
            f"Requested product_name: {payload.product_name}\n"
            f"Rows:\n{json.dumps(safe_rows, default=str, indent=2)}"
        ),
        expected_output=(
            "Valid JSON with source_truth_summary (string), selected_product (object|null), "
            "selection_reason (string)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    if not response.get("selected_product") and safe_rows:
        response["selected_product"] = safe_rows[0]

    out = {
        "source_truth_summary": str(response.get("source_truth_summary", "No source truth summary.")),
        "selected_product": response.get("selected_product"),
        "selection_reason": str(response.get("selection_reason", "")),
    }
    _log_event(
        run_id,
        "REVIEWER_OUTPUT",
        {"has_selected_product": bool(out["selected_product"])},
    )
    return out


def _scrape_walmart_product_data(product_url: str, run_id: str) -> dict[str, Any] | None:
    _log_event(run_id, "SCRAPER_START", {"product_url": product_url})
    scraper_fn = _load_testing_scraper()
    data = scraper_fn(product_url)
    _log_event(run_id, "SCRAPER_COMPLETE", {"has_data": bool(data)})
    return data


def _load_testing_scraper():
    testing_path = Path(__file__).resolve().parents[2] / "testing.py"
    if not testing_path.exists():
        logger.warning("Scraper script not found at %s; using built-in fallback.", testing_path)
        return _fallback_scrape_walmart_product

    import importlib.util

    spec = importlib.util.spec_from_file_location("backend_testing", testing_path)
    if spec is None or spec.loader is None:
        logger.warning("Unable to load backend/testing.py; using built-in fallback scraper.")
        return _fallback_scrape_walmart_product

    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        logger.warning("backend/testing.py could not be imported (%s); using fallback scraper.", exc)
        return _fallback_scrape_walmart_product

    if not hasattr(module, "scrape_walmart_product"):
        logger.warning("backend/testing.py missing scrape_walmart_product(url); using fallback scraper.")
        return _fallback_scrape_walmart_product
    return getattr(module, "scrape_walmart_product")


def _fallback_scrape_walmart_product(product_url: str) -> dict[str, Any]:
    """
    Lightweight, dependency-free scraper fallback.

    It attempts a best-effort HTML fetch and extracts a few common metadata
    fields. If the request fails, it still returns a structured payload so the
    marketing workflow can continue with the product reference and URL.
    """
    parsed = urlparse(product_url)
    fallback = {
        "product_url": product_url,
        "domain": parsed.netloc,
        "page_title": "",
        "meta_description": "",
        "h1": "",
        "summary": "",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Fallback scraper used because the dedicated scraper module was unavailable or failed.",
        ],
    }

    if not product_url:
        fallback["notes"].append("No product URL was provided.")
        return fallback

    try:
        request = Request(
            product_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "")
            html = response.read(200_000).decode("utf-8", errors="replace")
            fallback["content_type"] = content_type
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        fallback["notes"].append(f"Fetch failed: {exc}")
        return fallback

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        flags=re.I | re.S,
    )
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)

    def _clean(value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    page_title = _clean(title_match.group(1)) if title_match else ""
    meta_description = _clean(desc_match.group(1)) if desc_match else ""
    h1 = _clean(h1_match.group(1)) if h1_match else ""

    fallback["page_title"] = page_title
    fallback["meta_description"] = meta_description
    fallback["h1"] = h1
    fallback["summary"] = " ".join(part for part in [page_title, h1, meta_description] if part)
    if not fallback["summary"]:
        fallback["notes"].append("HTML fetched, but no obvious product metadata was found.")
    return fallback


def _scraper_analysis(
    payload: InstagramFlowInput,
    scraped_data: dict[str, Any] | None,
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    response = _run_agent_json(
        role="Scraper Agent",
        goal=(
            "Summarize Walmart product page findings and extract marketing-relevant claims "
            "without inventing facts."
        ),
        backstory=(
            "You process scraped e-commerce product content and isolate credible product details "
            "for campaign drafting."
        ),
        description=(
            "Use the scraped payload below.\n"
            "Return JSON with keys: scraped_summary, web_claims, product_angle.\n"
            "- web_claims must be a short list of factual claims only.\n\n"
            f"Scraped Data:\n{json.dumps(scraped_data or {}, default=str, indent=2)}"
        ),
        expected_output=(
            "Valid JSON with scraped_summary (string), web_claims (array of strings), "
            "product_angle (string)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    claims = response.get("web_claims")
    if not isinstance(claims, list):
        claims = []
    claims = [str(c) for c in claims][:8]

    out = {
        "scraped_summary": str(response.get("scraped_summary", "No scraper summary.")),
        "web_claims": claims,
        "product_angle": str(response.get("product_angle", "")),
    }
    _log_event(run_id, "SCRAPER_ANALYSIS_OUTPUT", {"claims": len(out["web_claims"])})
    return out


def _summary_validation(
    payload: InstagramFlowInput,
    controller_plan: dict[str, Any],
    reviewer_output: dict[str, Any],
    scraped_output: dict[str, Any],
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    response = _run_agent_json(
        role="Summary Validator Agent",
        goal=(
            "Merge reviewer and scraper evidence, then validate alignment with user campaign intent."
        ),
        backstory=(
            "You gate the pipeline by ensuring merged product context supports the requested "
            "marketing direction before content generation."
        ),
        description=(
            "Merge evidence and validate user expectation alignment.\n"
            "Return JSON keys: aligned, alignment_notes, merged_summary, gaps.\n"
            "- aligned should be true only if summary supports user intent.\n\n"
            f"Controller Plan:\n{json.dumps(controller_plan, default=str, indent=2)}\n\n"
            f"User Method Input:\n{payload.method_section_content}\n\n"
            f"User Campaign Caption Seed:\n{payload.product_marketing_campaign_caption}\n\n"
            f"Reviewer Output:\n{json.dumps(reviewer_output, default=str, indent=2)}\n\n"
            f"Scraper Output:\n{json.dumps(scraped_output, default=str, indent=2)}"
        ),
        expected_output=(
            "Valid JSON with aligned (bool), alignment_notes (string), merged_summary (string), "
            "gaps (array of strings)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    out = {
        "aligned": bool(response.get("aligned")),
        "alignment_notes": str(response.get("alignment_notes", "")),
        "merged_summary": str(response.get("merged_summary", "")),
        "gaps": [str(x) for x in response.get("gaps", [])] if isinstance(response.get("gaps"), list) else [],
    }
    _log_event(run_id, "SUMMARY_VALIDATION_OUTPUT", {"aligned": out["aligned"]})
    return out


def _realign_summary(
    payload: InstagramFlowInput,
    validation_output: dict[str, Any],
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    response = _run_agent_json(
        role="Summary Validator Agent",
        goal=(
            "Realign the merged summary with user campaign intent while preserving factual accuracy."
        ),
        backstory=(
            "You transform factual product evidence into a campaign-aligned brief without "
            "inventing unsupported claims."
        ),
        description=(
            "A previous validation found misalignment.\n"
            "Return JSON with keys: aligned, alignment_notes, merged_summary, gaps.\n"
            "- aligned should be true if revised summary now supports the campaign theme.\n"
            "- keep summary factual and grounded.\n\n"
            f"Original Validation Output:\n{json.dumps(validation_output, default=str, indent=2)}\n\n"
            f"User Method Input:\n{payload.method_section_content}\n\n"
            f"User Campaign Caption Seed:\n{payload.product_marketing_campaign_caption}"
        ),
        expected_output=(
            "Valid JSON with aligned (bool), alignment_notes (string), merged_summary (string), gaps (array)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    gaps = response.get("gaps")
    if not isinstance(gaps, list):
        gaps = []

    return {
        "aligned": True if response.get("merged_summary") else bool(response.get("aligned")),
        "alignment_notes": str(response.get("alignment_notes", "Summary realigned.")),
        "merged_summary": str(
            response.get("merged_summary")
            or validation_output.get("merged_summary")
            or "Campaign summary generated."
        ),
        "gaps": [str(x) for x in gaps],
    }


def _generate_content(
    payload: InstagramFlowInput,
    validation_output: dict[str, Any],
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    response = _run_agent_json(
        role="Content Agent",
        goal=(
            "Generate Instagram-ready marketing content including visualizer prompt and a "
            "shareable marketing description from validated product context."
        ),
        backstory=(
            "You create social-native product campaigns balancing clarity, conversion intent, "
            "and brand consistency."
        ),
        description=(
            "Generate initial campaign content.\n"
            "Return JSON with keys: visual_prompt, marketing_description, posts.\n"
            "posts must be an array of exactly 3 objects with: headline, caption, hashtags, "
            "visualDirection, cta.\n\n"
            f"Merged Summary:\n{validation_output.get('merged_summary', '')}\n\n"
            f"User Method:\n{payload.method_section_content}\n\n"
            f"Campaign Caption Seed:\n{payload.product_marketing_campaign_caption}"
        ),
        expected_output=(
            "Valid JSON with visual_prompt (string), marketing_description (string), posts (array of 3 post objects)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    out = {
        "visual_prompt": str(response.get("visual_prompt", "")),
        "marketing_description": str(response.get("marketing_description", "")),
        "posts": response.get("posts", []),
    }
    _log_event(run_id, "CONTENT_OUTPUT", {"has_posts": isinstance(out["posts"], list)})
    return out


def _critique_content(
    payload: InstagramFlowInput,
    content_output: dict[str, Any],
    round_idx: int,
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    # Detailed criteria — each one demands a specific, quotable finding
    criteria = [
        {
            "id": "hook_strength",
            "rule": "The first sentence of every caption must be a hook that creates immediate curiosity, urgency, or a bold claim. It must NOT start with the brand/product name or a generic opener like 'Introducing' or 'Meet'.",
            "bad_example": "Introducing our new wireless earbuds — great sound for everyday use.",
            "good_example": "You've been tolerating bad audio. That ends today.",
        },
        {
            "id": "claim_grounding",
            "rule": "Every factual claim (price, specs, features, availability) must trace directly to the validated product summary. Flag any claim that is invented, approximate, or unverifiable from the source data.",
            "bad_example": "Industry-leading 40-hour battery life.",
            "good_example": "Up to 28 hours of playback — verified from product specs.",
        },
        {
            "id": "cta_specificity",
            "rule": "Each post must have exactly ONE call-to-action. It must name the specific action (e.g. 'Tap the link in bio', 'DM us SIZE', 'Save this post'). Generic CTAs like 'Shop now' or 'Check it out' are NOT acceptable.",
            "bad_example": "Shop now and save!",
            "good_example": "Tap the link in bio to grab yours before the weekend sale ends.",
        },
        {
            "id": "adjective_ban",
            "rule": "Remove all empty adjectives: amazing, great, incredible, awesome, perfect, best, premium, top-quality, cutting-edge, revolutionary. Each descriptor must be replaced with a concrete product fact or sensory detail.",
            "bad_example": "Premium sound quality for an amazing listening experience.",
            "good_example": "40mm drivers tuned for bass that hits without muddying the mids.",
        },
        {
            "id": "hashtag_relevance",
            "rule": "Hashtags must be specific to the product category, campaign theme, or target audience. Reject generic filler tags (#Love, #Happy, #Life, #Instagood, #PhotoOfTheDay). At least 60% of hashtags must be niche or product-specific.",
            "bad_example": "#Love #Happy #ShopNow #Instagood #Life",
            "good_example": "#WirelessEarbuds #WorkFromHome #AudioGear #NoiseCancel",
        },
        {
            "id": "caption_length",
            "rule": "Instagram captions should be 3-5 lines max for the visible portion before 'more'. The hook line must stand alone in the first line. Body copy must not exceed 2 sentences. Verbose copy kills engagement.",
            "bad_example": "A four-paragraph caption describing every feature in full detail.",
            "good_example": "Hook line.\n\nOne-sentence benefit. One-sentence proof.\n\nCTA.",
        },
        {
            "id": "visual_post_alignment",
            "rule": "The visualDirection for each post must describe a specific scene, composition, or creative treatment — not just 'product on white background'. It should include subject, setting, lighting mood, and focal point.",
            "bad_example": "Clean product shot on white background.",
            "good_example": "Overhead flat-lay on weathered oak desk: earbuds case open, coffee cup left-side, soft morning light from right, negative space for caption overlay.",
        },
    ]

    response = _run_agent_json(
        role="Critique Agent",
        goal=(
            "Deliver a surgical, post-by-post critique of the Instagram content. "
            "Quote the exact text that fails each criterion and provide a concrete rewrite. "
            "No generic feedback. No vague suggestions. Every must_fix item must name the post "
            "index (0, 1, or 2), the criterion id, the offending text in quotes, and the rewrite."
        ),
        backstory=(
            "You are a senior social media creative director who has reviewed thousands of "
            "Instagram campaigns. You reject vague feedback. Your notes are always specific, "
            "actionable, and tied to exact copy from the content under review. "
            "You never say 'improve the hook' — you say what is wrong with this hook and "
            "provide the replacement line."
        ),
        description=(
            f"CRITIQUE ROUND {round_idx} — read every post caption word-by-word.\n\n"
            "INSTRUCTIONS:\n"
            "1. For each failing criterion, quote the EXACT offending text from the content.\n"
            "2. State which specific rule it violates (use the criterion id).\n"
            "3. Provide a concrete rewrite of that specific text — not a general direction.\n"
            "4. Score each criterion 0-10 in criterion_scores (object with criterion ids as keys).\n"
            "5. Compute overall score as the mean of criterion scores.\n\n"
            "must_fix format (each item is a string):\n"
            '  "[Post N][criterion_id] FOUND: \'<exact quoted text>\' → FIX: <rewrite>\'"\n\n'
            "Return JSON with keys: round_feedback, must_fix, criterion_scores, score.\n\n"
            f"CRITERIA:\n{json.dumps(criteria, indent=2)}\n\n"
            f"CONTENT TO CRITIQUE:\n{json.dumps(content_output, default=str, indent=2)}\n\n"
            f"CAMPAIGN INTENT (user method):\n{payload.method_section_content}\n\n"
            f"CAMPAIGN CAPTION SEED:\n{payload.product_marketing_campaign_caption}"
        ),
        expected_output=(
            "Valid JSON with: "
            "round_feedback (string — 2-3 sentence overall assessment), "
            "must_fix (array of specific fix strings in the format [Post N][criterion_id] FOUND/FIX), "
            "criterion_scores (object: criterion_id -> score 0-10), "
            "score (number 0-10, mean of criterion_scores)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    must_fix = response.get("must_fix")
    if not isinstance(must_fix, list):
        must_fix = []

    criterion_scores = response.get("criterion_scores")
    if not isinstance(criterion_scores, dict):
        criterion_scores = {}

    # Derive score from criterion_scores if present, else fall back to reported score
    if criterion_scores:
        vals = [v for v in criterion_scores.values() if isinstance(v, (int, float))]
        computed_score = round(sum(vals) / len(vals), 2) if vals else float(response.get("score", 6.0))
    else:
        computed_score = float(response.get("score", 6.0))

    out = {
        "round_feedback": str(response.get("round_feedback", "Content reviewed.")),
        "must_fix": [str(x) for x in must_fix][:20],
        "criterion_scores": {str(k): float(v) for k, v in criterion_scores.items() if isinstance(v, (int, float))},
        "score": computed_score,
    }
    _log_event(run_id, "CRITIQUE_OUTPUT", {"round": round_idx, "score": out["score"], "fixes": len(out["must_fix"])})
    return out


def _revise_content(
    payload: InstagramFlowInput,
    content_output: dict[str, Any],
    critique_output: dict[str, Any],
    round_idx: int,
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    response = _run_agent_json(
        role="Content Agent",
        goal=(
            "Revise campaign content using critique instructions while preserving product truth."
        ),
        backstory=(
            "You iterate copy and visual direction fast, improving clarity and conversion quality."
        ),
        description=(
            f"Revise content for critique round {round_idx}.\n"
            "Return JSON with keys: visual_prompt, marketing_description, posts.\n"
            "posts must remain an array of 3 post objects.\n\n"
            f"Previous Content:\n{json.dumps(content_output, default=str, indent=2)}\n\n"
            f"Critique:\n{json.dumps(critique_output, default=str, indent=2)}\n\n"
            f"Campaign Caption Seed:\n{payload.product_marketing_campaign_caption}"
        ),
        expected_output=(
            "Valid JSON with visual_prompt (string), marketing_description (string), posts (array of 3 post objects)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )

    out = {
        "visual_prompt": str(response.get("visual_prompt", content_output.get("visual_prompt", ""))),
        "marketing_description": str(
            response.get("marketing_description", content_output.get("marketing_description", ""))
        ),
        "posts": response.get("posts", content_output.get("posts", [])),
    }
    _log_event(run_id, "CONTENT_REVISION_OUTPUT", {"round": round_idx})
    return out


def _format_final_output(
    payload: InstagramFlowInput,
    validation_output: dict[str, Any],
    content_output: dict[str, Any],
    iteration_notes: list[str],
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    response = _run_agent_json(
        role="Formatter Agent",
        goal=(
            "Format final campaign output into stable API schema for frontend rendering."
        ),
        backstory=(
            "You transform internal agent outputs into clean productized response contracts."
        ),
        description=(
            "Format final output JSON with keys: strategySummary, iterationNotes, posts.\n"
            "posts must include headline, caption, hashtags, visualDirection, cta.\n\n"
            f"Validated Summary:\n{validation_output.get('merged_summary', '')}\n\n"
            f"Iteration Notes:\n{json.dumps(iteration_notes, indent=2)}\n\n"
            f"Content Output:\n{json.dumps(content_output, default=str, indent=2)}\n\n"
            f"Campaign Seed:\n{payload.product_marketing_campaign_caption}"
        ),
        expected_output=(
            "Valid JSON object with strategySummary (string), iterationNotes (array of strings), posts (array)."
        ),
        run_id=run_id,
        memory_context=memory_context,
    )
    _log_event(run_id, "FORMATTER_OUTPUT", {"keys": list(response.keys())})
    return response


def _run_agent_json(
    role: str,
    goal: str,
    backstory: str,
    description: str,
    expected_output: str,
    run_id: str,
    memory_context: list[str],
) -> dict[str, Any]:
    memory_block = _memory_block(memory_context)
    full_description = (
        f"{description}\n\n"
        "Crew Memory Context:\n"
        f"{memory_block}\n\n"
        "Return only a valid JSON object. Do not include markdown fences."
    )

    _log_event(run_id, "AGENT_TASK_START", {"agent": role})
    agent = Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        allow_delegation=False,
        verbose=False,
        llm="gpt-4o-mini",
    )
    task = Task(
        description=full_description,
        expected_output=expected_output,
        agent=agent,
    )
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
        memory=True,
    )
    result = crew.kickoff()
    parsed = _extract_json_object(result)
    _log_event(run_id, "AGENT_TASK_COMPLETE", {"agent": role, "keys": list(parsed.keys())})
    return parsed


def _extract_json_object(result: Any) -> dict[str, Any]:
    raw = getattr(result, "raw", None) or str(result)
    if not raw:
        raise InstagramFlowError("Crew output was empty.")

    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise InstagramFlowError(f"Unable to parse JSON from crew output: {cleaned[:300]}")

    try:
        parsed = json.loads(match.group(0))
    except Exception as exc:
        raise InstagramFlowError(f"Invalid JSON in crew output: {exc}") from exc

    if not isinstance(parsed, dict):
        raise InstagramFlowError("Crew output JSON root must be an object.")

    return parsed


def _normalize_posts(raw_posts: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_posts, list):
        return []

    out: list[dict[str, Any]] = []
    for idx, post in enumerate(raw_posts[:3], start=1):
        if not isinstance(post, dict):
            continue
        hashtags = post.get("hashtags")
        if not isinstance(hashtags, list):
            hashtags = ["#ProductSpotlight", "#ShopNow"]
        out.append(
            {
                "headline": str(post.get("headline", f"Post Option {idx}")),
                "caption": str(post.get("caption", "")),
                "hashtags": [str(x) for x in hashtags][:10],
                "visualDirection": str(
                    post.get("visualDirection")
                    or post.get("visual_direction")
                    or "Product-forward visual composition."
                ),
                "cta": str(post.get("cta", "Explore this product today.")),
            }
        )
    return out


def _default_posts(content_output: dict[str, Any], payload: InstagramFlowInput) -> list[dict[str, Any]]:
    marketing_description = str(content_output.get("marketing_description", "")).strip()
    visual_prompt = str(content_output.get("visual_prompt", "")).strip()
    product_ref = _product_reference(payload)
    return [
        {
            "headline": "Product Spotlight",
            "caption": (
                f"{payload.product_marketing_campaign_caption}\n\n"
                f"{marketing_description or 'Built for practical everyday value.'}\n"
                f"Featured: {product_ref}"
            ),
            "hashtags": ["#ProductSpotlight", "#ShopNow", "#InstagramFinds"],
            "visualDirection": visual_prompt or "Hero product frame with benefit overlay.",
            "cta": "Check this product in our catalog now.",
        },
        {
            "headline": "Lifestyle Angle",
            "caption": (
                f"{payload.product_marketing_campaign_caption}\n\n"
                "Designed for real routines and real results."
            ),
            "hashtags": ["#Lifestyle", "#BrandStory", "#ShopNow"],
            "visualDirection": "In-use lifestyle scene with clear product focus.",
            "cta": "Save this post and discover the product.",
        },
        {
            "headline": "Why People Pick It",
            "caption": (
                f"{payload.product_marketing_campaign_caption}\n\n"
                "Performance, value, and design in one pick."
            ),
            "hashtags": ["#NewDrop", "#ProductValue", "#MustHave"],
            "visualDirection": "Carousel sequence: problem, solution, result.",
            "cta": "Open catalog and get yours today.",
        },
    ]


# ── Utilities ─────────────────────────────────────────────────────────────────

def _product_reference(payload: InstagramFlowInput) -> str:
    if payload.product_item_sk is not None:
        return f"Item SK {payload.product_item_sk}"
    return (payload.product_name or "").strip() or "Unknown Product"


def _payload_summary(payload: InstagramFlowInput) -> dict[str, Any]:
    return {
        "retrieval_enabled": payload.retrieval_enabled,
        "critique_rounds": payload.critique_rounds,
        "product_ref": _product_reference(payload),
        "method_len": len(payload.method_section_content or ""),
        "caption_len": len(payload.product_marketing_campaign_caption or ""),
    }


def _memory_block(memory_context: list[str]) -> str:
    if not memory_context:
        return "- No prior memory."
    recent = memory_context[-12:]
    return "\n".join([f"- {line}" for line in recent])


def _remember(memory_context: list[str], label: str, content: Any) -> None:
    text = str(content)
    if len(text) > 1200:
        text = text[:1200] + "...(truncated)"
    memory_context.append(f"{label}: {text}")


def _log_comm(run_id: str, sender: str, receiver: str, intent: str, content: Any) -> None:
    _log_event(
        run_id,
        "AGENT_COMM",
        {
            "from": sender,
            "to": receiver,
            "intent": intent,
            "content": content,
        },
    )


def _log_event(run_id: str, event: str, data: Any) -> None:
    envelope = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "event": event,
        "data": data,
    }
    logger.info("[INSTAGRAM_FLOW] %s", json.dumps(envelope, default=str))
