"""Core utilities, constants, cache, dataclasses, and shared helpers for thought_engine."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time as _time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.db import (
    create_timeline_post,
    get_timeline_posts,
)
from app.event_bus import event_bus

logger = logging.getLogger("app.thought_engine")

TRIGGERS_YAML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "thought_triggers.yaml")

# Mention pattern: @agent_name
MENTION_RE = re.compile(r"@(\w+)")

# ── TTL Cache ──

class TTLCache:
    """Dict-based cache with per-key expiry."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if _time.monotonic() > expires_at:
            del self._data[key]
            return None
        logger.debug("cache hit: %s", key)
        return value

    def set(self, key: str, value: object, ttl: float) -> None:
        self._data[key] = (_time.monotonic() + ttl, value)

    def clear(self) -> None:
        self._data.clear()


_cache = TTLCache()

# Cache TTLs (seconds)
_CACHE_TTL_PIPELINE = 60
_CACHE_TTL_POSTS = 30
_CACHE_TTL_PERSONALITY = 3600

# Post quality limits
MAX_THOUGHT_LENGTH = 500
MAX_REPLY_LENGTH = 3000

# ── Swarm System ──
SWARM_MAX_ACTIVATIONS = 8
SWARM_QUEUE_TIMEOUT = 5

# Max length for swarm replies
MAX_SWARM_REPLY_LENGTH = 400
MAX_DYNAMIC_REPLY_LENGTH = 3000

# Dynamic agent caps
DYNAMIC_AGENT_CAP = 4
DYNAMIC_DEBATE_CAP = 3
BUILDER_CAP_PER_POST = 3


# ── Dataclasses ──

@dataclass
class AgentRequest:
    """A request for an agent to join the swarm."""
    agent_name: str
    task: str
    urgency: str = "normal"
    requested_by: str = "router"
    wave: int = 1


@dataclass
class DynamicAgent:
    """A research curator assigned to investigate a specific angle of a topic."""
    agent_id: str
    display_name: str
    avatar: str
    expertise: str
    opinion_seed: str
    tone: str
    search_queries: list = None

    def __post_init__(self):
        if self.search_queries is None:
            self.search_queries = []


@dataclass
class AgentAssignment:
    """A single agent assignment from the router."""
    name: str
    prompt: str
    tools: bool = False
    invented: bool = False
    display_name: str = ""
    avatar: str = ""
    expertise: str = ""
    _backbone_agent: str = ""  # Real DNA agent powering this character
    _depth: str = "moderate"  # Per-character depth: light, moderate, deep


@dataclass
class ResponsePlan:
    """Router output: how to respond to a user's post."""
    agents: list[AgentAssignment]
    interactive: bool = False
    depth: str = "moderate"
    use_swarm: bool = False


@dataclass
class BuilderState:
    """Tracks a background tutorial builder task."""
    builder_id: str
    post_id: int
    title: str
    agent_id: str
    percent: int = 0
    stage: str = "queued"
    material_id: int | None = None


_active_builders: dict[str, BuilderState] = {}


@dataclass
class SwarmState:
    """Tracks one swarm lifecycle per post."""
    post_id: int
    parent_id: int | None
    user_content: str
    activation_count: int = 0
    max_activations: int = SWARM_MAX_ACTIVATIONS
    responded_agents: set = field(default_factory=set)
    pending_requests: asyncio.Queue = field(default_factory=asyncio.Queue)
    dynamic_agents: dict = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def can_activate(self) -> bool:
        async with self._lock:
            return self.activation_count < self.max_activations

    async def record_activation(self, agent_name: str) -> bool:
        async with self._lock:
            if self.activation_count >= self.max_activations:
                return False
            self.activation_count += 1
            self.responded_agents.add(agent_name)
            return True

    def has_responded(self, agent_name: str) -> bool:
        return agent_name in self.responded_agents


# ── Shared Helpers ──

def _enforce_quality(content: str, max_length: int = MAX_THOUGHT_LENGTH) -> str:
    """Light cleanup: fix rendering artifacts, enforce max length."""
    content = re.sub(r"\(source[^)]*\)", "", content).strip()
    content = re.sub(r"\[source\]", "", content, flags=re.IGNORECASE).strip()
    content = re.sub(r"\n{3,}", "\n\n", content)
    if len(content) > max_length:
        truncated = content[:max_length]
        last_period = truncated.rfind(".")
        last_excl = truncated.rfind("!")
        cut = max(last_period, last_excl)
        if cut > max_length // 2:
            content = truncated[: cut + 1]
        else:
            content = truncated.rstrip() + "..."
    return content.strip()


def _system_context() -> str:
    """Return current date/time and identity context to inject into all agent prompts."""
    now = datetime.now(timezone.utc)
    return (
        f"Current date and time: {now.strftime('%A, %B %d, %Y at %H:%M UTC')} (year {now.year}).\n"
        f"CRITICAL: Today is {now.year}. Your training data is from 2023-2024. DO NOT cite outdated stats or news.\n"
        "You are an agent in The Nexus — a living intelligence collective where dynamic agents "
        "emerge, collaborate, and dissolve based on missions. Messages from 'user' or '👤 You' are "
        "from the HUMAN operator (the Master). All other named participants are AI agents like you.\n"
        "IDENTITY RULES:\n"
        "- You have a unique agent ID. Own it. Sign your work.\n"
        "- Be direct, specific, and data-driven. No filler, no corporate speak.\n"
        "- Disagree with other agents when the evidence warrants it. Consensus through conflict.\n"
        "- Reference other agents by name when building on or challenging their work.\n"
        f"- ALWAYS use web_search for current events/trends. Use year {now.year} in queries.\n"
        "- NEVER cite statistics from 2023 or earlier without searching for current data first.\n"
        "- Your reputation depends on the quality of your contributions. Mediocrity is not tolerated."
    )


def _system_context_slim() -> str:
    """Compact system context for router/scheduler calls."""
    now = datetime.now(timezone.utc)
    return (
        f"Date: {now.strftime('%Y-%m-%d %H:%M UTC')} (year {now.year}). "
        f"Training data is outdated (2023-2024). Use web_search for current info. "
        "You are part of The Nexus AI collective. 'user' = human operator. "
        f"Be direct, data-driven, ALWAYS use {now.year} in web searches."
    )


async def _build_agent_context() -> str:
    """Build compact context string with pipeline data and recent activity."""
    cached = _cache.get("agent_context")
    if cached is not None:
        return cached

    parts = []
    try:
        from app.db import get_jobs_pipeline
        pipeline = _cache.get("pipeline")
        if pipeline is None:
            pipeline = await get_jobs_pipeline()
            _cache.set("pipeline", pipeline, _CACHE_TTL_PIPELINE)
        counts = {s: len(j) for s, j in pipeline.items() if j}
        if counts:
            parts.append("Pipeline: " + ", ".join(f"{s}={c}" for s, c in counts.items()))
        saved = pipeline.get("saved", [])[:3]
        if saved:
            parts.append("Recent: " + "; ".join(f"{j.get('title','?')}@{j.get('company','?')}" for j in saved))
        interviews = pipeline.get("interview", [])
        if interviews:
            parts.append("Interviews: " + "; ".join(f"{j.get('title','?')}@{j.get('company','?')}" for j in interviews[:3]))
        offers = pipeline.get("offer", [])
        if offers:
            parts.append("Offers: " + "; ".join(f"{j.get('title','?')}@{j.get('company','?')}" for j in offers[:2]))
    except Exception:
        pass

    try:
        recent_posts = _cache.get("recent_posts")
        if recent_posts is None:
            recent_posts = await get_timeline_posts(limit=3, top_level_only=True)
            _cache.set("recent_posts", recent_posts, _CACHE_TTL_POSTS)
        if recent_posts:
            summaries = [f"{p['agent']}:{p['content'][:60]}" for p in recent_posts]
            parts.append("Recent: " + " | ".join(summaries))
    except Exception:
        pass

    result = "\n".join(parts) if parts else ""
    _cache.set("agent_context", result, _CACHE_TTL_POSTS)
    return result


def _get_tools_for_agent(agent_name: str) -> list:
    """Get the tool objects assigned to an agent in bots.yaml."""
    try:
        from app.bot_config import get_bots_config
        from app.tools import TOOL_REGISTRY
        bots_config = get_bots_config()
        cfg = bots_config.bots.get(agent_name)
        if not cfg:
            return []
        return [TOOL_REGISTRY[t] for t in cfg.tools if t in TOOL_REGISTRY]
    except Exception:
        return []
