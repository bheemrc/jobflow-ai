"""Shared state and helpers for routers.

This module contains:
- Global graph instance management
- Bot validation helpers
- Session ID generation
- Timeline sorting utilities
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from math import log

logger = logging.getLogger(__name__)

# Global graph instance - set by lifespan in main.py
_graph = None


def set_graph(graph) -> None:
    """Set the global graph instance (called from main.py lifespan)."""
    global _graph
    _graph = graph


def get_graph():
    """Get the global graph instance."""
    return _graph


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return uuid.uuid4().hex[:16]


# ── Bot Validation ──

_bot_start_timestamps: dict[str, datetime] = {}
_VALID_BOT_NAME = re.compile(r"^[a-z][a-z0-9_]{2,29}$")


def validate_bot_name(name: str) -> tuple[bool, str]:
    """Validate a bot name. Returns (is_valid, error_message)."""
    if not _VALID_BOT_NAME.match(name):
        return False, "Bot name must be 3-30 chars, start with letter, only lowercase + underscore"
    return True, ""


def check_bot_rate_limit(name: str, cooldown_seconds: int = 5) -> tuple[bool, str]:
    """Check if a bot can be started (rate limiting). Returns (can_start, error_message)."""
    now = datetime.now()
    last_start = _bot_start_timestamps.get(name)
    if last_start and (now - last_start).total_seconds() < cooldown_seconds:
        return False, f"Bot {name} was started recently, please wait"
    return True, ""


def record_bot_start(name: str) -> None:
    """Record that a bot was started (for rate limiting)."""
    _bot_start_timestamps[name] = datetime.now()


# ── Graph Resume Helper ──

async def resume_graph_for_thread(
    thread_id: str,
    command_value: dict,
    user_id: str,
) -> dict:
    """Resume graph execution at an interrupt point."""
    from langgraph.types import Command
    from app.user_context import current_user_id

    current_user_id.set(user_id)
    config = {"configurable": {"thread_id": f"{user_id}:{thread_id}"}}

    graph = get_graph()
    if not graph:
        return {"error": "Graph not initialized"}

    response_text = ""
    async for event in graph.astream_events(
        Command(resume=command_value),
        config=config,
        version="v2",
    ):
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if hasattr(chunk, "content") and chunk.content:
                response_text += chunk.content

    return {"resumed": True, "response": response_text}


# ── Timeline Sorting Utilities ──

def _parse_iso(dt_val) -> datetime | None:
    """Parse ISO datetime string or return datetime as-is."""
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    try:
        return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
    except Exception:
        return None


def _hot_score(votes: int, created_at_str) -> float:
    """Calculate hot score for ranking (engagement + recency weighted)."""
    sign = 1 if votes > 0 else -1 if votes < 0 else 0
    order = log(max(abs(votes), 1), 10)
    created = _parse_iso(created_at_str)
    if not created:
        return 0.0
    epoch = datetime(1970, 1, 1)
    if created.tzinfo:
        from datetime import timezone
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    seconds = (created - epoch).total_seconds()
    return sign * order + seconds / 45000


def sort_timeline_posts(posts: list[dict], sort: str) -> list[dict]:
    """Sort timeline posts by specified method."""
    if sort == "hot":
        return sorted(
            posts,
            key=lambda p: (p.get("pinned", False), _hot_score(p.get("votes", 0), p.get("created_at"))),
            reverse=True,
        )
    elif sort == "top":
        return sorted(
            posts,
            key=lambda p: (p.get("pinned", False), p.get("votes", 0)),
            reverse=True,
        )
    else:  # "new" or default
        return sorted(
            posts,
            key=lambda p: (p.get("pinned", False), p.get("created_at", "")),
            reverse=True,
        )
