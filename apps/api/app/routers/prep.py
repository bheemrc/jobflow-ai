"""Prep materials endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import settings
from app.db import get_prep_materials, get_prep_material_by_id, delete_prep_material, create_prep_material
from app.models import PrepMaterialCreate
from app.user_context import get_user_id
from app.thought_engine import _orchestrate_dynamic_swarm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prep", tags=["prep"])


@router.post("/materials")
async def create_prep_material_endpoint(body: PrepMaterialCreate, user_id: str = Depends(get_user_id)):
    """Create a prep material from the frontend."""
    # db.create_prep_material expects content as a dict (JSON-serializable)
    content = body.content if isinstance(body.content, dict) else {"text": body.content}
    material_id = await create_prep_material(
        material_type=body.material_type,
        title=body.title,
        content=content,
        company=body.company,
        role=body.role,
        agent_source=body.agent_source,
        resources=body.resources,
        user_id=user_id,
    )
    return {"ok": True, "id": material_id}


@router.get("/materials")
async def list_prep_materials(
    material_type: str | None = None,
    company: str | None = None,
    limit: int = 50,
    user_id: str = Depends(get_user_id),
):
    """List saved prep materials with optional filters."""
    materials = await get_prep_materials(
        material_type=material_type, company=company, limit=limit, user_id=user_id,
    )
    return {"materials": materials}


@router.get("/materials/{material_id}")
async def get_prep_material(material_id: int, user_id: str = Depends(get_user_id)):
    """Get a single prep material by ID."""
    material = await get_prep_material_by_id(material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Prep material not found")
    return {"material": material}


@router.delete("/materials/{material_id}")
async def delete_prep_material_endpoint(material_id: int, user_id: str = Depends(get_user_id)):
    """Delete a prep material."""
    material = await get_prep_material_by_id(material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Prep material not found")
    await delete_prep_material(material_id)
    return {"ok": True}


@router.post("/generate")
async def prep_generate(request: Request, user_id: str = Depends(get_user_id)):
    """Generate a field manual (tutorial) on a topic using the research swarm + builder pipeline.

    Creates a virtual post (negative ID) and runs the full swarm with skip_timeline=True
    so research agents run and builder creates material, but no posts appear on the timeline.
    The prep page can watch builder progress via /timeline/stream SSE events.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    topic = (body.get("topic") or "").strip()
    if not topic or len(topic) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters")
    if len(topic) > 500:
        raise HTTPException(status_code=400, detail="Topic must be 500 characters or fewer")

    focus = (body.get("focus") or "").strip()

    # Prepend focus directive so the swarm agents and builder respect the user's intent
    if focus:
        content = f"[FOCUS: {focus}] {topic}"
    else:
        content = topic

    # Generate a negative virtual post_id (timestamp-based, guaranteed unique)
    virtual_post_id = -abs(int(time.time() * 1000) % 2_000_000_000)

    # Build a virtual post dict that mimics a real timeline post
    virtual_post = {
        "id": virtual_post_id,
        "agent": "user",
        "post_type": "question",
        "content": content,
        "parent_id": None,
        "context": {"source": "prep_generate", "focus": focus},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Run the swarm as a background task with skip_timeline=True
    asyncio.create_task(_orchestrate_dynamic_swarm(virtual_post, skip_timeline=True))

    return {"ok": True, "virtual_post_id": virtual_post_id, "topic": topic}


@router.post("/discover")
async def prep_discover(user_id: str = Depends(get_user_id)):
    """Search the web for LeetCode problems, DSA tutorials, and blogs, then organize via AI."""
    from openai import AsyncOpenAI

    if not settings.tavily_api_key:
        raise HTTPException(status_code=400, detail="Tavily API key not configured")
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")

    # 1. Run 3 Tavily searches in parallel
    from tavily import TavilyClient
    tavily = TavilyClient(api_key=settings.tavily_api_key)

    queries = [
        "best leetcode problems to practice this week blind 75 neetcode 2026",
        "data structures algorithms tutorial blog guide 2026",
        "coding interview preparation tips patterns system design 2026",
    ]

    def _search(q: str) -> list[dict]:
        try:
            resp = tavily.search(query=q, max_results=8)
            return resp.get("results", [])
        except Exception as e:
            logger.warning("Tavily search failed for %r: %s", q, e)
            return []

    results = await asyncio.gather(
        asyncio.to_thread(_search, queries[0]),
        asyncio.to_thread(_search, queries[1]),
        asyncio.to_thread(_search, queries[2]),
    )

    # 2. Combine and deduplicate by URL
    seen_urls: set[str] = set()
    all_results: list[dict] = []
    for batch in results:
        for item in batch:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append({
                    "title": item.get("title", ""),
                    "url": url,
                    "content": (item.get("content") or "")[:500],
                })

    if not all_results:
        raise HTTPException(status_code=502, detail="No search results returned")

    # 3. Call OpenAI to organize results
    oai = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = """You are a coding interview prep curator. Given raw web search results,
extract and organize the most useful resources into 3 categories.
For each item provide a 1-sentence summary of why it's useful.
Tag problems with difficulty (easy/medium/hard) and topics.
Limit: up to 5 problems, 3 tutorials, 3 blog posts.
Only include items with valid URLs from the search results.

Return JSON with this exact structure:
{
  "problems": [{"title": "...", "difficulty": "easy|medium|hard", "topics": ["..."], "url": "...", "summary": "..."}],
  "tutorials": [{"title": "...", "url": "...", "source": "...", "summary": "..."}],
  "blog_posts": [{"title": "...", "url": "...", "source": "...", "summary": "..."}]
}"""

    search_text = json.dumps(all_results, indent=2)
    completion = await oai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Here are the raw search results:\n\n{search_text}"},
        ],
    )

    try:
        organized = json.loads(completion.choices[0].message.content)
    except (json.JSONDecodeError, IndexError, AttributeError):
        raise HTTPException(status_code=502, detail="Failed to parse AI response")

    problems = organized.get("problems", [])[:5]
    tutorials = organized.get("tutorials", [])[:3]
    blog_posts = organized.get("blog_posts", [])[:3]

    # 4. Save as prep material
    today = date.today().strftime("%B %d, %Y")
    content = {
        "problems": problems,
        "tutorials": tutorials,
        "blog_posts": blog_posts,
    }
    material_id = await create_prep_material(
        material_type="leetcode",
        title=f"Daily Picks — {today}",
        content=content,
        agent_source="discovery",
        user_id=user_id,
    )

    return {
        "material_id": material_id,
        "date": today,
        "problems": problems,
        "tutorials": tutorials,
        "blog_posts": blog_posts,
    }
