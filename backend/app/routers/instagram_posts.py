"""
POST /api/instagram-posts/generate

Independent marketing workflow for generating Instagram campaign post ideas.
Uses crewAI when available and falls back to deterministic generation when
crewAI is not installed/configured.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger("routers.instagram_posts")
router = APIRouter(prefix="/api/instagram-posts", tags=["instagram-posts"])


class InstagramWorkflowRequest(BaseModel):
    retrieval_enabled: bool = Field(..., alias="retrievalEnabled")
    critique_rounds: int = Field(..., ge=0, le=5, alias="critiqueRounds")
    product_link: HttpUrl = Field(..., alias="productLink")
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
    workflow: str
    used_crewai: bool = Field(..., alias="usedCrewAI")
    strategy_summary: str = Field(..., alias="strategySummary")
    iteration_notes: list[str] = Field(default_factory=list, alias="iterationNotes")
    posts: list[GeneratedPost]

    model_config = {"populate_by_name": True}


@router.post(
    "/generate",
    response_model=InstagramWorkflowResponse,
    summary="Generate Instagram marketing posts from campaign settings",
)
async def generate_instagram_posts(
    payload: InstagramWorkflowRequest,
) -> InstagramWorkflowResponse:
    if payload.critique_rounds > 5:
        raise HTTPException(status_code=400, detail="Critique rounds cannot exceed 5")

    try:
        return _run_crewai_workflow(payload)
    except Exception as exc:
        logger.warning("crewAI workflow unavailable, using fallback: %s", exc)
        return _fallback_response(payload, reason=str(exc))


def _run_crewai_workflow(payload: InstagramWorkflowRequest) -> InstagramWorkflowResponse:
    from crewai import Agent, Crew, Process, Task  # type: ignore

    strategist = Agent(
        role="Instagram Campaign Strategist",
        goal=(
            "Build a concise campaign strategy for product marketing based on "
            "the provided method and caption guidance."
        ),
        backstory=(
            "You translate product context into social-first campaign direction "
            "with a clear audience, hook, and positioning."
        ),
        allow_delegation=False,
        verbose=False,
    )

    copywriter = Agent(
        role="Instagram Copywriter",
        goal=(
            "Produce high-conversion Instagram post drafts with clear hooks, "
            "scannable copy, and strong CTA."
        ),
        backstory=(
            "You write short-form social copy that aligns with campaign goals "
            "and maintains a cohesive brand tone."
        ),
        allow_delegation=False,
        verbose=False,
    )

    critic = Agent(
        role="Social Content Critic",
        goal=(
            "Review and improve post quality over the requested critique rounds "
            "without changing core campaign intent."
        ),
        backstory=(
            "You refine clarity, emotional pull, visual pairing quality, and "
            "CTA strength while preserving brand consistency."
        ),
        allow_delegation=False,
        verbose=False,
    )

    strategy_task = Task(
        description=(
            "Create a strategy summary using these inputs:\n"
            f"- Retrieval enabled: {payload.retrieval_enabled}\n"
            f"- Product link: {payload.product_link}\n"
            f"- Method section: {payload.method_section_content}\n"
            f"- Campaign caption seed: {payload.product_marketing_campaign_caption}\n\n"
            "Return a short strategy with audience, message angle, tone, and "
            "content structure guidance."
        ),
        expected_output="A concise strategy brief in plain text.",
        agent=strategist,
    )

    post_task = Task(
        description=(
            "Generate exactly 3 Instagram post options as JSON array. "
            "Each object must include: headline, caption, hashtags (list), "
            "visualDirection, cta. Keep captions practical and marketable."
        ),
        expected_output="A valid JSON array with 3 post objects.",
        agent=copywriter,
        context=[strategy_task],
    )

    critique_task = Task(
        description=(
            f"Critique and improve the generated posts for {payload.critique_rounds} rounds. "
            "At each round, improve hook strength, readability, and CTA clarity. "
            "Output final JSON object with keys: strategySummary, iterationNotes, posts. "
            "iterationNotes must be a list of concise notes per round."
        ),
        expected_output=(
            "A valid JSON object with strategySummary (string), iterationNotes "
            "(array of strings), and posts (array of 3 post objects)."
        ),
        agent=critic,
        context=[strategy_task, post_task],
    )

    crew = Crew(
        agents=[strategist, copywriter, critic],
        tasks=[strategy_task, post_task, critique_task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    parsed = _parse_crewai_result(result)

    strategy_summary = parsed.get("strategySummary") or _build_strategy_summary(payload)
    iteration_notes = parsed.get("iterationNotes") or _default_iteration_notes(payload)
    posts = _normalize_posts(parsed.get("posts"), payload)

    return InstagramWorkflowResponse(
        workflow="crewai_instagram_posts_v1",
        usedCrewAI=True,
        strategySummary=strategy_summary,
        iterationNotes=iteration_notes,
        posts=posts,
    )


def _parse_crewai_result(result: Any) -> dict[str, Any]:
    text = getattr(result, "raw", None) or str(result)
    if not text:
        raise ValueError("crewAI returned empty result")

    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()

    try:
        maybe_obj = json.loads(cleaned)
        if isinstance(maybe_obj, dict):
            return maybe_obj
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("Unable to parse crewAI JSON output")

    return json.loads(match.group(0))


def _normalize_posts(raw_posts: Any, payload: InstagramWorkflowRequest) -> list[GeneratedPost]:
    if not isinstance(raw_posts, list):
        return _default_posts(payload)

    normalized: list[GeneratedPost] = []
    for idx, post in enumerate(raw_posts[:3], start=1):
        if not isinstance(post, dict):
            continue

        hashtags = post.get("hashtags")
        if not isinstance(hashtags, list):
            hashtags = _default_hashtags(payload)

        normalized.append(
            GeneratedPost(
                headline=str(post.get("headline") or f"Campaign Post {idx}"),
                caption=str(post.get("caption") or payload.product_marketing_campaign_caption),
                hashtags=[str(x) for x in hashtags][:8],
                visualDirection=str(
                    post.get("visualDirection")
                    or post.get("visual_direction")
                    or "Product-focused lifestyle visual with clear focal subject."
                ),
                cta=str(post.get("cta") or "Tap the link to explore the product."),
            )
        )

    if normalized:
        return normalized

    return _default_posts(payload)


def _fallback_response(
    payload: InstagramWorkflowRequest, reason: str
) -> InstagramWorkflowResponse:
    return InstagramWorkflowResponse(
        workflow="crewai_instagram_posts_v1",
        usedCrewAI=False,
        strategySummary=_build_strategy_summary(payload),
        iterationNotes=[f"Fallback mode active: {reason}"] + _default_iteration_notes(payload),
        posts=_default_posts(payload),
    )


def _build_strategy_summary(payload: InstagramWorkflowRequest) -> str:
    retrieval_line = (
        "Retrieval is enabled to ground claims from linked product context."
        if payload.retrieval_enabled
        else "Retrieval is disabled; messaging is based only on provided campaign guidance."
    )
    return (
        f"{retrieval_line} Position the product with a clear benefit-first hook, "
        "use short social-native copy, and keep the CTA singular and explicit."
    )


def _default_iteration_notes(payload: InstagramWorkflowRequest) -> list[str]:
    notes: list[str] = []
    if payload.critique_rounds == 0:
        return ["No critique rounds requested."]

    for i in range(1, payload.critique_rounds + 1):
        notes.append(
            f"Round {i}: tightened hook clarity, improved CTA precision, and reduced caption noise."
        )
    return notes


def _default_hashtags(payload: InstagramWorkflowRequest) -> list[str]:
    return [
        "#NewDrop",
        "#ProductSpotlight",
        "#ShopNow",
        "#InstagramFinds",
        "#BrandStory",
    ]


def _default_posts(payload: InstagramWorkflowRequest) -> list[GeneratedPost]:
    base_caption = payload.product_marketing_campaign_caption.strip()
    method_hint = payload.method_section_content.strip()
    hint_excerpt = method_hint[:140] + ("..." if len(method_hint) > 140 else "")

    posts = [
        GeneratedPost(
            headline="Fresh Product Highlight",
            caption=(
                f"{base_caption}\n\nWhy it matters: {hint_excerpt}\n"
                f"Explore here: {payload.product_link}"
            ),
            hashtags=_default_hashtags(payload),
            visualDirection="Clean hero shot + benefit overlay in first frame.",
            cta="Tap to explore the full product details.",
        ),
        GeneratedPost(
            headline="Lifestyle Benefit Angle",
            caption=(
                f"{base_caption}\n\nBuilt for daily use with practical value and style. "
                "Save this post and share with a friend who needs this."
            ),
            hashtags=_default_hashtags(payload),
            visualDirection="Lifestyle in-use frame with warm, authentic context.",
            cta="Comment if you want a full feature breakdown.",
        ),
        GeneratedPost(
            headline="Social Proof Variant",
            caption=(
                f"{base_caption}\n\nPeople choose this for reliability, simplicity, and results. "
                f"See more: {payload.product_link}"
            ),
            hashtags=_default_hashtags(payload),
            visualDirection="Carousel concept: problem -> product -> result.",
            cta="Open the link and grab yours today.",
        ),
    ]
    return posts
