"""Proactive agent triggers — background checks that run at session startup.

These triggers inspect the user's state and inject proactive suggestions
into the conversation before the main graph processes the user's message.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.db import get_conn

logger = logging.getLogger(__name__)


async def check_triggers(user_id: str = "") -> list[dict]:
    """Run all proactive trigger checks and return notifications.

    Returns:
        List of trigger dicts: {type, title, message, priority}
    """
    triggers: list[dict] = []

    stale = await stale_application_check(user_id)
    if stale:
        triggers.append(stale)

    interview = await interview_reminder(user_id)
    if interview:
        triggers.append(interview)

    leetcode = await daily_leetcode_check(user_id)
    if leetcode:
        triggers.append(leetcode)

    return triggers


async def daily_leetcode_check(user_id: str = "") -> dict | None:
    """If user has active prep, suggest today's practice session."""
    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS cnt FROM saved_jobs WHERE status = 'interview' AND user_id = $1",
                user_id,
            )
            interview_count = row["cnt"] if row else 0

        if interview_count > 0:
            return {
                "type": "leetcode_reminder",
                "title": "Daily Practice",
                "message": (
                    f"You have {interview_count} job(s) in interview stage. "
                    "A daily coding practice session will keep you sharp."
                ),
                "priority": "medium",
            }
    except Exception as e:
        logger.debug("daily_leetcode_check error: %s", e)

    return None


async def stale_application_check(user_id: str = "") -> dict | None:
    """Flag jobs in 'applied' status with no activity >7 days."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        async with get_conn() as conn:
            rows = await conn.fetch("""
                SELECT title, company FROM saved_jobs
                WHERE status = 'applied'
                  AND user_id = $1
                  AND (updated_at < $2 OR (updated_at IS NULL AND saved_at < $2))
                LIMIT 5
            """, user_id, cutoff)

        if not rows:
            return None

        job_list = ", ".join(
            f"{r['title']} at {r['company']}" for r in rows
        )
        return {
            "type": "stale_application",
            "title": "Stale Applications",
            "message": (
                f"{len(rows)} application(s) have had no activity for 7+ days: "
                f"{job_list}. Consider following up or updating their status."
            ),
            "priority": "low",
        }
    except Exception as e:
        logger.debug("stale_application_check error: %s", e)

    return None


async def interview_reminder(user_id: str = "") -> dict | None:
    """If jobs are in 'interview' stage, proactively suggest prep."""
    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                "SELECT title, company FROM saved_jobs WHERE status = 'interview' AND user_id = $1 LIMIT 3",
                user_id,
            )

        if not rows:
            return None

        job_list = ", ".join(
            f"{r['title']} at {r['company']}" for r in rows
        )
        return {
            "type": "interview_reminder",
            "title": "Interview Prep Needed",
            "message": (
                f"You have interview(s) lined up: {job_list}. "
                "Want me to build a prep package for any of these?"
            ),
            "priority": "high",
        }
    except Exception as e:
        logger.debug("interview_reminder error: %s", e)

    return None
