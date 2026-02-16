"""Timeline endpoints for the agent social feed."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import fastapi
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.db import (
    get_timeline_posts,
    get_timeline_post_by_id,
    get_timeline_replies,
    get_timeline_reply_counts,
    add_timeline_reaction,
    pin_timeline_post,
    delete_timeline_post,
    vote_timeline_post,
    get_timeline_vote_counts,
    get_agent_reputation,
    recall_agent_memories,
    get_agent_memory_stats,
)
from app.models import TimelinePostCreate, TimelineReplyCreate, TimelineReactionAdd
from app.user_context import get_user_id, current_user_id
from app.event_bus import event_bus
from app.sse import format_bot_event
from app.thought_engine import create_user_post, create_user_reply, get_all_personalities

router = APIRouter(prefix="/timeline", tags=["timeline"])


# ── Helper functions ──

def _parse_iso(dt_str: str) -> datetime:
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return datetime.now(timezone.utc)


def _hot_score(post: dict, now: datetime) -> float:
    votes = post.get("votes", 0) or 0
    replies = post.get("reply_count", 0) or 0
    created_at = _parse_iso(post.get("created_at", ""))
    age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
    engagement = votes + replies * 2
    recency_boost = max(0.0, 5.0 * (2.71828 ** (-age_hours / 2.0)))
    return (engagement + recency_boost) / ((age_hours + 2.0) ** 1.5)


def _sort_timeline_posts(posts: list[dict], sort: str | None) -> list[dict]:
    if not sort:
        return posts
    now = datetime.now(timezone.utc)
    def pinned_first(p: dict) -> int:
        return 0 if p.get("pinned") else 1
    if sort == "new":
        return sorted(
            posts,
            key=lambda p: (pinned_first(p), _parse_iso(p.get("created_at", ""))),
            reverse=True,
        )
    if sort == "top":
        return sorted(
            posts,
            key=lambda p: (pinned_first(p), p.get("votes", 0) or 0),
            reverse=True,
        )
    if sort == "active":
        return sorted(
            posts,
            key=lambda p: (pinned_first(p), (p.get("reply_count", 0) or 0) + len(p.get("reactions", {}))),
            reverse=True,
        )
    if sort == "hot":
        return sorted(
            posts,
            key=lambda p: (pinned_first(p), _hot_score(p, now)),
            reverse=True,
        )
    return posts


# ── Routes ──

@router.get("")
async def list_timeline(
    limit: int = 50,
    offset: int = 0,
    agent: str | None = None,
    post_type: str | None = None,
    sort: str | None = None,
    user_id: str = Depends(get_user_id),
):
    """Get timeline feed with optional filters and server-side sorting."""
    current_user_id.set(user_id)
    posts = await get_timeline_posts(
        limit=limit, offset=offset, agent=agent, post_type=post_type, user_id=user_id,
    )
    # Enrich with reply counts and votes
    post_ids = [p["id"] for p in posts]
    reply_counts = await get_timeline_reply_counts(post_ids, user_id=user_id)
    vote_data = await get_timeline_vote_counts(post_ids, user_id=user_id)
    for p in posts:
        p["reply_count"] = reply_counts.get(p["id"], 0)
        vd = vote_data.get(p["id"], {})
        p["votes"] = vd.get("votes", 0)
        p["user_vote"] = vd.get("user_vote", 0)
    posts = _sort_timeline_posts(posts, sort)
    has_more = len(posts) == limit
    return {"posts": posts, "total": len(posts), "limit": limit, "offset": offset, "has_more": has_more}


@router.post("")
async def create_timeline_post_endpoint(body: TimelinePostCreate, user_id: str = Depends(get_user_id)):
    """Create a new user post on the timeline."""
    current_user_id.set(user_id)
    post = await create_user_post(content=body.content, context=body.context)
    return {"ok": True, "post": post}


@router.get("/agents")
async def get_timeline_agents(user_id: str = Depends(get_user_id)):
    """Get agent personality profiles for the timeline."""
    personalities = get_all_personalities()
    # Add user personality
    agents = {"user": {
        "display_name": "You",
        "avatar": "👤",
        "voice": "",
        "bio": "That's you!",
    }}
    agents.update(personalities)
    return {"agents": agents}


@router.get("/stats")
async def get_timeline_stats(user_id: str = Depends(get_user_id)):
    """Get timeline rate limiting stats and health info."""
    from app.thought_engine.rate_limiting import (
        _rate_limit_date, _agent_daily_posts, _global_daily_posts,
        DAILY_POST_LIMIT_PER_AGENT, DAILY_POST_LIMIT_GLOBAL,
    )
    return {
        "date": _rate_limit_date,
        "global_posts_today": _global_daily_posts,
        "global_limit": DAILY_POST_LIMIT_GLOBAL,
        "per_agent": {
            agent: {"posts_today": count, "limit": DAILY_POST_LIMIT_PER_AGENT}
            for agent, count in dict(_agent_daily_posts).items()
        },
    }


@router.get("/stream")
async def timeline_stream(request: fastapi.Request, user_id: str = Depends(get_user_id)):
    """SSE stream for live timeline updates."""
    current_user_id.set(user_id)
    last_event_id_str = request.headers.get("Last-Event-ID")
    last_event_id = int(last_event_id_str) if last_event_id_str else None
    try:
        limit = int(request.query_params.get("limit", "20"))
    except Exception:
        limit = 20
    sort = request.query_params.get("sort")

    async def event_generator():
        # Send recent posts as initial state
        posts = await get_timeline_posts(limit=limit, user_id=user_id)
        post_ids = [p["id"] for p in posts]
        reply_counts, vote_data = await asyncio.gather(
            get_timeline_reply_counts(post_ids, user_id=user_id),
            get_timeline_vote_counts(post_ids, user_id=user_id),
        )
        for p in posts:
            p["reply_count"] = reply_counts.get(p["id"], 0)
            vd = vote_data.get(p["id"], {})
            p["votes"] = vd.get("votes", 0)
            p["user_vote"] = vd.get("user_vote", 0)
        posts = _sort_timeline_posts(posts, sort)
        yield format_bot_event({"type": "timeline_state", "posts": posts})

        # Stream live events (filter to timeline events only)
        async for ev in event_bus.subscribe(last_event_id=last_event_id):
            if ev.get("type") in (
                # Timeline events
                "timeline_post", "timeline_reaction", "timeline_vote",
                "agent_thinking", "heartbeat",
                # Swarm events
                "swarm_started", "swarm_phase", "agent_requested", "swarm_complete",
                # Builder events
                "builder_dispatched", "builder_progress", "builder_complete",
                # Research session events
                "research_phase", "research_agents_spawned",
                "agent_search_started", "agent_search_result", "agent_finding",
                "debate_started", "debate_turn",
                "research_synthesis", "research_synthesis_chunk",
                "research_complete", "research_error",
            ):
                eid = ev.get("event_id", "")
                yield f"id: {eid}\ndata: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/agents/reputation")
async def get_agents_reputation(user_id: str = Depends(get_user_id)):
    """Get reputation scores for all agents that have posted."""
    posts = await get_timeline_posts(limit=500)
    agent_keys = list({p["agent"] for p in posts if p["agent"] != "user"})
    reputations = {}
    for key in agent_keys:
        reputations[key] = await get_agent_reputation(key)
    return {"reputations": reputations}


@router.get("/agents/memories")
async def get_agents_memories_endpoint(agent: str | None = None, limit: int = 10, user_id: str = Depends(get_user_id)):
    """Get agent memories. If agent is specified, return memories for that agent."""
    if agent:
        memories = await recall_agent_memories(agent, limit=limit, user_id=user_id)
        return {"agent": agent, "memories": memories}
    stats = await get_agent_memory_stats(user_id=user_id)
    return {"memory_stats": stats}


@router.get("/{post_id}")
async def get_timeline_post_endpoint(post_id: int, user_id: str = Depends(get_user_id)):
    """Get a single post with its replies."""
    current_user_id.set(user_id)
    post = await get_timeline_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    replies = await get_timeline_replies(post_id)
    return {"post": post, "replies": replies}


@router.post("/{post_id}/reply")
async def reply_to_post(post_id: int, body: TimelineReplyCreate, user_id: str = Depends(get_user_id)):
    """Reply to a timeline post (user reply, may trigger agent response)."""
    current_user_id.set(user_id)
    parent = await get_timeline_post_by_id(post_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Post not found")
    post = await create_user_reply(content=body.content, parent_id=post_id)
    return {"ok": True, "post": post}


@router.post("/{post_id}/react")
async def react_to_post(post_id: int, body: TimelineReactionAdd, user_id: str = Depends(get_user_id)):
    """Add a reaction to a timeline post."""
    current_user_id.set(user_id)
    post = await get_timeline_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    updated = await add_timeline_reaction(post_id, body.agent, body.emoji)
    await event_bus.publish({
        "type": "timeline_reaction",
        "post_id": post_id,
        "agent": body.agent,
        "emoji": body.emoji,
    })
    return {"ok": True, "post": updated}


@router.post("/{post_id}/vote")
async def vote_on_post(post_id: int, request: Request, user_id: str = Depends(get_user_id)):
    """Cast a vote on a timeline post. Body: {"direction": 1|-1|0, "voter": "user"}"""
    current_user_id.set(user_id)
    post = await get_timeline_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        body = await request.json()
    except Exception:
        body = {}
    direction = body.get("direction", 0)
    voter = user_id  # Use actual Clerk user ID as voter
    result = await vote_timeline_post(post_id, voter, direction, user_id=user_id)
    await event_bus.publish({
        "type": "timeline_vote",
        "post_id": post_id,
        "voter": voter,
        "direction": direction,
        "votes": result["votes"],
    })
    return {"ok": True, **result}


@router.patch("/{post_id}/pin")
async def pin_timeline_post_endpoint(post_id: int, request: Request, user_id: str = Depends(get_user_id)):
    """Toggle pin on a timeline post."""
    post = await get_timeline_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        body = await request.json()
    except Exception:
        body = {}
    pinned = body.get("pinned", True)
    await pin_timeline_post(post_id, pinned)
    return {"ok": True, "pinned": pinned}


@router.delete("/{post_id}")
async def delete_timeline_post_endpoint(post_id: int, user_id: str = Depends(get_user_id)):
    """Delete a timeline post."""
    post = await get_timeline_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await delete_timeline_post(post_id)
    return {"ok": True}
