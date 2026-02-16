"""Rate limiting for agent posts — daily caps, per-thread cooldowns."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from app.event_bus import event_bus

logger = logging.getLogger("app.thought_engine")

# Daily post caps per agent and global
DAILY_POST_LIMIT_PER_AGENT = 30
DAILY_POST_LIMIT_GLOBAL = 200
THREAD_COOLDOWN_MINUTES = 3

# In-memory rate limit tracking (resets daily)
_rate_limit_date: str = ""
_agent_daily_posts: dict[str, int] = defaultdict(int)
_global_daily_posts: int = 0
# {(agent, parent_id): last_reply_datetime}
_thread_cooldowns: dict[tuple[str, int], datetime] = {}


def _reset_rate_limits_if_new_day() -> None:
    """Reset daily counters if the date has changed."""
    global _rate_limit_date, _agent_daily_posts, _global_daily_posts, _thread_cooldowns
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today != _rate_limit_date:
        _rate_limit_date = today
        _agent_daily_posts = defaultdict(int)
        _global_daily_posts = 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        _thread_cooldowns = {k: v for k, v in _thread_cooldowns.items() if v > cutoff}


def _publish_rate_limit_event(agent: str, reason: str) -> None:
    """Fire-and-forget publish of rate_limit_hit event to the event bus."""
    try:
        asyncio.get_event_loop().create_task(event_bus.publish({
            "type": "rate_limit_hit",
            "agent": agent,
            "reason": reason,
            "daily_posts": _agent_daily_posts.get(agent, 0),
            "global_posts": _global_daily_posts,
        }))
    except RuntimeError:
        pass


def _check_rate_limit(agent: str, parent_id: int | None = None, user_initiated: bool = False) -> bool:
    """Check if an agent is allowed to post. Returns True if allowed."""
    _reset_rate_limits_if_new_day()

    if _agent_daily_posts[agent] >= DAILY_POST_LIMIT_PER_AGENT:
        logger.info("Rate limit: %s hit daily cap (%d)", agent, DAILY_POST_LIMIT_PER_AGENT)
        _publish_rate_limit_event(agent, "agent_daily_cap")
        return False

    global _global_daily_posts
    if _global_daily_posts >= DAILY_POST_LIMIT_GLOBAL:
        logger.info("Rate limit: global daily cap reached (%d)", DAILY_POST_LIMIT_GLOBAL)
        _publish_rate_limit_event(agent, "global_daily_cap")
        return False

    if parent_id is not None and not user_initiated:
        key = (agent, parent_id)
        last = _thread_cooldowns.get(key)
        if last and (datetime.now(timezone.utc) - last) < timedelta(minutes=THREAD_COOLDOWN_MINUTES):
            logger.info("Rate limit: %s thread cooldown for post %d", agent, parent_id)
            return False

    return True


def _record_post(agent: str, parent_id: int | None = None) -> None:
    """Record that an agent posted (for rate limiting)."""
    _reset_rate_limits_if_new_day()
    _agent_daily_posts[agent] += 1
    global _global_daily_posts
    _global_daily_posts += 1
    if parent_id is not None:
        _thread_cooldowns[(agent, parent_id)] = datetime.now(timezone.utc)
