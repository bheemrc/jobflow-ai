"""Agent personality profiles and trigger initialization from YAML."""

from __future__ import annotations

import logging

import yaml

from app.db import upsert_thought_trigger

from .core import _cache, _CACHE_TTL_PERSONALITY, TRIGGERS_YAML_PATH

logger = logging.getLogger("app.thought_engine")


def _load_triggers_config() -> dict:
    """Load thought_triggers.yaml config. Cached for 1 hour."""
    cached = _cache.get("triggers_config")
    if cached is not None:
        return cached
    try:
        with open(TRIGGERS_YAML_PATH, "r") as f:
            config = yaml.safe_load(f) or {}
            _cache.set("triggers_config", config, _CACHE_TTL_PERSONALITY)
            return config
    except FileNotFoundError:
        logger.warning("thought_triggers.yaml not found at %s", TRIGGERS_YAML_PATH)
        return {}


def get_agent_personality(agent_name: str) -> dict:
    """Get personality profile for an agent."""
    config = _load_triggers_config()
    personalities = config.get("personalities", {})
    return personalities.get(agent_name, {
        "display_name": agent_name.replace("_", " ").title(),
        "avatar": "🤖",
        "voice": "professional and helpful",
        "bio": "",
    })


def get_all_personalities() -> dict[str, dict]:
    """Get all agent personality profiles."""
    config = _load_triggers_config()
    return config.get("personalities", {})


async def initialize_triggers() -> None:
    """Load triggers from YAML into the database on startup."""
    config = _load_triggers_config()
    triggers = config.get("triggers", [])
    count = 0
    for t in triggers:
        trigger_type = t.get("trigger_type", "event")
        agent = t.get("agent", "")
        prompt = t.get("prompt", "")
        cooldown = t.get("cooldown_minutes", 30)

        if trigger_type == "event":
            trigger_config = {"event": t.get("event", "")}
        elif trigger_type == "schedule":
            trigger_config = {"schedule": t.get("schedule", "")}
        else:
            trigger_config = {}

        if agent and prompt:
            await upsert_thought_trigger(
                trigger_type=trigger_type,
                trigger_config=trigger_config,
                agent=agent,
                prompt_template=prompt,
                cooldown_minutes=cooldown,
            )
            count += 1
    logger.info("Initialized %d thought triggers from YAML", count)
