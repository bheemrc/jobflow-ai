"""Live Research Session API endpoints.

Provides user-controlled, focused research with parallel agent execution
and real-time streaming of progress.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.user_context import get_user_id, current_user_id
from app.research import (
    run_research_session,
    get_session_status,
    cancel_session,
    session_count,
    MAX_CONCURRENT_SESSIONS,
)
from app.research.engine import _create_logged_task

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    """Request to start a research session."""
    topic: str


class ResearchResponse(BaseModel):
    """Response from starting a research session."""
    session_id: str
    status: str


@router.post("/start", response_model=ResearchResponse)
async def start_research_session(
    body: ResearchRequest,
    user_id: str = Depends(get_user_id),
) -> ResearchResponse:
    """Start a focused research session on a single topic.

    The session runs asynchronously. Use /sessions/{session_id} to check status
    or subscribe to SSE events filtered by session_id for real-time updates.
    """
    current_user_id.set(user_id)

    if not body.topic or len(body.topic.strip()) < 3:
        raise HTTPException(status_code=400, detail="Topic must be at least 3 characters")

    if len(body.topic) > 500:
        raise HTTPException(status_code=400, detail="Topic must be less than 500 characters")

    if session_count() >= MAX_CONCURRENT_SESSIONS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent research sessions (max {MAX_CONCURRENT_SESSIONS}). Try again later.",
        )

    session_id = uuid.uuid4().hex[:12]

    _create_logged_task(
        run_research_session(session_id, body.topic.strip(), user_id),
        name=f"research-{session_id}",
    )

    return ResearchResponse(session_id=session_id, status="started")


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Depends(get_user_id),
) -> dict:
    """Get status of a research session."""
    status = get_session_status(session_id, user_id=user_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return status


@router.delete("/sessions/{session_id}")
async def stop_session(
    session_id: str,
    user_id: str = Depends(get_user_id),
) -> dict:
    """Cancel a running research session."""
    success = cancel_session(session_id, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Session not found or already completed",
        )
    return {"ok": True, "session_id": session_id, "status": "cancelled"}
