"""LeetCode progress queries."""

from __future__ import annotations

from .core import get_conn


async def get_leetcode_progress_data(user_id: str = "") -> dict:
    async with get_conn() as conn:
        progress = await conn.fetch("SELECT * FROM leetcode_progress WHERE user_id = $1 ORDER BY last_attempt DESC NULLS LAST", user_id)
        mastery = await conn.fetch("SELECT * FROM leetcode_mastery WHERE user_id = $1 ORDER BY topic", user_id)
        total_solved = sum(1 for r in progress if r["solved"])
        streak = 0
        return {
            "total_solved": total_solved,
            "total_attempted": len(progress),
            "streak": streak,
            "problems": [dict(r) for r in progress],
            "mastery": [dict(r) for r in mastery],
        }


async def log_leetcode_attempt(
    problem_id: int,
    problem_title: str,
    difficulty: str,
    topic: str,
    solved: bool,
    time_minutes: int | None = None,
    user_id: str = "",
) -> None:
    async with get_conn() as conn:
        await conn.execute("""
            INSERT INTO leetcode_progress (problem_id, problem_title, difficulty, topic, solved, time_minutes, attempts, last_attempt, user_id)
            VALUES ($1, $2, $3, $4, $5, $6, 1, NOW(), $7)
            ON CONFLICT (problem_id) DO UPDATE SET
                solved = COALESCE(leetcode_progress.solved, FALSE) OR $5,
                time_minutes = COALESCE($6, leetcode_progress.time_minutes),
                attempts = leetcode_progress.attempts + 1,
                last_attempt = NOW()
        """, problem_id, problem_title, difficulty, topic, solved, time_minutes, user_id)

        await conn.execute("""
            INSERT INTO leetcode_mastery (topic, level, problems_solved, problems_attempted, updated_at, user_id)
            VALUES ($1, $2, $3, 1, NOW(), $5)
            ON CONFLICT (topic) DO UPDATE SET
                problems_attempted = leetcode_mastery.problems_attempted + 1,
                problems_solved = leetcode_mastery.problems_solved + (CASE WHEN $4 THEN 1 ELSE 0 END),
                level = LEAST(100, (leetcode_mastery.problems_solved + (CASE WHEN $4 THEN 1 ELSE 0 END)) * 10),
                updated_at = NOW()
        """, topic, (10 if solved else 0), (1 if solved else 0), solved, user_id)
