"""LeetCode progress and practice endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.db import get_leetcode_progress_data, log_leetcode_attempt as db_log_leetcode_attempt
from app.models import LeetCodeAttempt
from app.user_context import get_user_id

router = APIRouter(prefix="/leetcode", tags=["leetcode"])


@router.get("/progress")
async def leetcode_progress(user_id: str = Depends(get_user_id)):
    """Get LeetCode practice progress."""
    return await get_leetcode_progress_data(user_id=user_id)


@router.post("/attempt")
async def leetcode_attempt(body: LeetCodeAttempt, user_id: str = Depends(get_user_id)):
    """Log a LeetCode problem attempt."""
    await db_log_leetcode_attempt(
        problem_id=body.problem_id,
        problem_title=body.problem_title,
        difficulty=body.difficulty,
        topic=body.topic,
        solved=body.solved,
        time_minutes=body.time_minutes,
        user_id=user_id,
    )
    return {"ok": True, "problem_id": body.problem_id, "solved": body.solved}


@router.get("/daily")
async def leetcode_daily(user_id: str = Depends(get_user_id)):
    """Get today's recommended problems (stub)."""
    return {
        "problems": [
            {"id": 1, "title": "Two Sum", "difficulty": "easy", "topic": "arrays"},
            {"id": 322, "title": "Coin Change", "difficulty": "medium", "topic": "dp"},
            {"id": 200, "title": "Number of Islands", "difficulty": "medium", "topic": "graphs"},
        ]
    }
