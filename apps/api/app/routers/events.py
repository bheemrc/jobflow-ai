"""Global event stream endpoint."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.db import get_all_agent_states, get_pending_approvals, get_recent_activity
from app.user_context import get_user_id
from app.sse import format_sse

router = APIRouter(tags=["events"])


@router.get("/events/stream")
async def global_events(user_id: str = Depends(get_user_id)):
    """Global SSE event stream for dashboard updates."""
    async def event_generator():
        # Send initial state
        agents = await get_all_agent_states(user_id=user_id)
        for a in agents:
            if "last_run" in a and hasattr(a["last_run"], "isoformat"):
                a["last_run"] = a["last_run"].isoformat() if a["last_run"] else None
        yield format_sse({"type": "agents_state", "agents": agents})

        approvals = await get_pending_approvals(user_id=user_id)
        for item in approvals:
            if "created_at" in item and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()
        yield format_sse({"type": "approvals_state", "approvals": approvals})

        activity = await get_recent_activity(10, user_id=user_id)
        for a in activity:
            if "created_at" in a and hasattr(a["created_at"], "isoformat"):
                a["created_at"] = a["created_at"].isoformat()
        yield format_sse({"type": "activity_state", "activity": activity})

        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            yield format_sse({"type": "heartbeat"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
