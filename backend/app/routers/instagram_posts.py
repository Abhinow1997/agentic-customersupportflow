"""
POST /api/instagram-posts/generate        — sync (full result at once)
POST /api/instagram-posts/generate-stream — SSE stream (events per agent stage)
POST /api/instagram-posts/generate-image  — DALL-E-2 image from visual prompt
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.instagram_crewai_flow import (
    AlignmentError,
    InstagramFlowError,
    InstagramFlowInput,
    run_instagram_crewai_flow,
)
from app.config import get_settings

router = APIRouter(prefix="/api/instagram-posts", tags=["instagram-posts"])
logger = logging.getLogger("routers.instagram_posts")


# ── Request / Response models ─────────────────────────────────────────────────

class InstagramWorkflowRequest(BaseModel):
    retrieval_enabled: bool = Field(..., alias="retrievalEnabled")
    critique_rounds: int = Field(..., ge=0, le=5, alias="critiqueRounds")
    product_item_sk: int | None = Field(None, alias="productItemSk")
    product_name: str | None = Field(None, alias="productName")
    method_section_content: str = Field(..., min_length=10, alias="methodSectionContent")
    product_marketing_campaign_caption: str = Field(
        ..., min_length=5, alias="productMarketingCampaignCaption"
    )
    model_config = {"populate_by_name": True}


class GeneratedPost(BaseModel):
    headline: str
    caption: str
    hashtags: list[str]
    visual_direction: str = Field(..., alias="visualDirection")
    cta: str
    model_config = {"populate_by_name": True}


class InstagramWorkflowResponse(BaseModel):
    run_id: str = Field(..., alias="runId")
    workflow: str
    used_crewai: bool = Field(..., alias="usedCrewAI")
    strategy_summary: str = Field(..., alias="strategySummary")
    iteration_notes: list[str] = Field(default_factory=list, alias="iterationNotes")
    posts: list[GeneratedPost]
    controller_plan: dict[str, Any] = Field(default_factory=dict, alias="controllerPlan")
    source_truth: str = Field("", alias="sourceTruth")
    scraped_summary: str = Field("", alias="scrapedSummary")
    visualizer_prompt: str = Field("", alias="visualizerPrompt")
    marketing_description: str = Field("", alias="marketingDescription")
    validation_result: dict[str, Any] = Field(default_factory=dict, alias="validationResult")
    agent_outputs: list[dict[str, Any]] = Field(default_factory=list, alias="agentOutputs")
    warnings: list[str] = Field(default_factory=list)
    model_config = {"populate_by_name": True}


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=1000)


class ImageGenerateResponse(BaseModel):
    image_url: str = Field(..., alias="imageUrl")
    prompt: str
    model: str
    size: str
    model_config = {"populate_by_name": True}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_flow_input(payload: InstagramWorkflowRequest) -> InstagramFlowInput:
    return InstagramFlowInput(
        retrieval_enabled=payload.retrieval_enabled,
        critique_rounds=payload.critique_rounds,
        product_item_sk=payload.product_item_sk,
        product_name=(payload.product_name or "").strip() or None,
        method_section_content=payload.method_section_content,
        product_marketing_campaign_caption=payload.product_marketing_campaign_caption,
    )


def _validate_product_ref(payload: InstagramWorkflowRequest) -> None:
    if payload.product_item_sk is None and not (payload.product_name or "").strip():
        raise HTTPException(status_code=400, detail="Provide either productItemSk or productName.")


# ── Sync endpoint ─────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=InstagramWorkflowResponse,
    summary="Generate Instagram posts (sync — full result returned at once)",
)
async def generate_instagram_posts(
    payload: InstagramWorkflowRequest,
) -> InstagramWorkflowResponse:
    _validate_product_ref(payload)
    flow_input = _build_flow_input(payload)
    try:
        result = run_instagram_crewai_flow(flow_input)
    except AlignmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InstagramFlowError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Instagram crew workflow failed: {exc}") from exc
    return InstagramWorkflowResponse.model_validate(result)


# ── Streaming SSE endpoint ────────────────────────────────────────────────────

@router.post(
    "/generate-stream",
    summary="Generate Instagram posts with live SSE agent events",
)
async def generate_instagram_posts_stream(
    payload: InstagramWorkflowRequest,
) -> StreamingResponse:
    _validate_product_ref(payload)
    flow_input = _build_flow_input(payload)

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    def event_callback(event: dict) -> None:
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)

    def run_in_thread() -> None:
        try:
            result = run_instagram_crewai_flow(flow_input, event_callback=event_callback)
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "flow_complete", "result": result}), loop
            )
        except (AlignmentError, InstagramFlowError) as exc:
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "flow_error", "error": str(exc)}), loop
            )
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "flow_error", "error": f"Workflow failed: {exc}"}), loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    async def event_stream() -> AsyncGenerator[str, None]:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── DALL-E image generation endpoint ─────────────────────────────────────────

@router.post(
    "/generate-image",
    response_model=ImageGenerateResponse,
    summary="Generate a visual suggestion image with DALL-E from the content agent's visual prompt",
)
async def generate_image(payload: ImageGenerateRequest) -> ImageGenerateResponse:
    settings = get_settings()

    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")

    # DALL-E-2 prompt length limit is 1000 chars; DALL-E-3 is 4000.
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

    logger.info(
        "DALLE_REQUEST model=%s size=%s prompt_len=%d",
        settings.DALLE_MODEL,
        settings.DALLE_IMAGE_SIZE,
        len(prompt),
    )

    try:
        # Run blocking OpenAI call in a thread so we don't block the event loop
        loop = asyncio.get_event_loop()
        image_url = await loop.run_in_executor(
            None,
            lambda: _call_dalle(
                api_key=settings.OPENAI_API_KEY,
                model=settings.DALLE_MODEL,
                prompt=prompt,
                size=settings.DALLE_IMAGE_SIZE,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("DALLE_ERROR %s", exc)
        raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}") from exc

    logger.info("DALLE_COMPLETE url_prefix=%s", image_url[:60] if image_url else "none")

    return ImageGenerateResponse.model_validate(
        {
            "imageUrl": image_url,
            "prompt": prompt,
            "model": settings.DALLE_MODEL,
            "size": settings.DALLE_IMAGE_SIZE,
        }
    )


def _call_dalle(api_key: str, model: str, prompt: str, size: str) -> str:
    """Synchronous DALL-E call — runs inside a thread executor."""
    from openai import OpenAI, BadRequestError

    client = OpenAI(api_key=api_key)
    try:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,  # type: ignore[arg-type]
            n=1,
            response_format="url",
        )
    except BadRequestError as exc:
        # Surface DALL-E content policy rejections clearly
        raise HTTPException(
            status_code=422,
            detail=f"DALL-E rejected the prompt (content policy): {exc}",
        ) from exc

    url = response.data[0].url
    if not url:
        raise ValueError("DALL-E returned an empty image URL.")
    return url
