"""Agent status and activity endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.db import get_all_agent_states, get_recent_activity
from app.user_context import get_user_id

router = APIRouter(tags=["agents"])


@router.get("/agents/status")
async def agent_status(user_id: str = Depends(get_user_id)):
    """Get all agent states."""
    states = await get_all_agent_states(user_id=user_id)
    for s in states:
        if "last_run" in s and hasattr(s["last_run"], "isoformat"):
            s["last_run"] = s["last_run"].isoformat() if s["last_run"] else None
    return {"agents": states}


@router.get("/activity")
async def activity_feed(user_id: str = Depends(get_user_id)):
    """Get recent activity log."""
    activity = await get_recent_activity(20, user_id=user_id)
    for a in activity:
        if "created_at" in a and hasattr(a["created_at"], "isoformat"):
            a["created_at"] = a["created_at"].isoformat()
    return {"activity": activity}
