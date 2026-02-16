"""Bot management tool: start, stop, pause, resume, create, list bots."""

from __future__ import annotations

import asyncio
import json
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def manage_bot(
    action: str,
    bot_name: str = "",
    bot_config: str = "{}",
) -> str:
    """Manage bots from within agent conversations — start, stop, pause, resume,
    create new bots, or list all bot states.

    Use this tool when you want to trigger another bot to do work, or when the user
    asks to create a new specialized bot based on your recommendations.

    Args:
        action: The action to perform — "start", "stop", "pause", "resume", "create", or "list".
        bot_name: The bot name (required for start/stop/pause/resume, used as name for create).
        bot_config: JSON string with bot configuration for "create" action. Fields:
                     display_name, description, model, temperature, max_tokens, tools (array),
                     prompt, schedule_type (interval/cron), schedule_hours, schedule_hour,
                     schedule_minute, requires_approval, timeout_minutes.

    Returns:
        JSON with the action result.
    """
    valid_actions = ("start", "stop", "pause", "resume", "create", "list")
    if action not in valid_actions:
        return json.dumps({"error": f"Invalid action. Must be one of: {', '.join(valid_actions)}"})

    try:
        from app.bot_manager import bot_manager

        if action == "list":
            states = bot_manager.get_all_states()
            return json.dumps({
                "action": "list",
                "bots": [
                    {
                        "name": s.get("name"),
                        "display_name": s.get("display_name"),
                        "status": s.get("status"),
                        "enabled": s.get("enabled"),
                        "last_run_at": s.get("last_run_at"),
                        "cooldown_until": s.get("cooldown_until"),
                        "runs_today": s.get("runs_today", 0),
                        "last_activated_by": s.get("last_activated_by"),
                        "total_runs": s.get("total_runs", 0),
                    }
                    for s in states
                ],
            })

        if not bot_name:
            return json.dumps({"error": f"bot_name is required for action '{action}'"})

        # For start/stop/pause/resume, bridge to async bot_manager methods
        if action in ("start", "stop", "pause", "resume"):
            loop = asyncio.get_event_loop()
            if action == "start":
                coro = bot_manager.start_bot(bot_name, trigger_type="agent")
            elif action == "stop":
                coro = bot_manager.stop_bot(bot_name)
            elif action == "pause":
                coro = bot_manager.pause_bot(bot_name)
            else:
                coro = bot_manager.resume_bot(bot_name)

            # LangChain tools run in a thread executor; schedule the coroutine on the event loop
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            result = future.result(timeout=30)
            return json.dumps({"action": action, "bot_name": bot_name, **result})

        # Create action
        if action == "create":
            try:
                config = json.loads(bot_config) if isinstance(bot_config, str) else bot_config
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON in bot_config"})

            from app.bot_config import BotConfig, BotScheduleConfig

            schedule_type = config.get("schedule_type", "interval")
            if schedule_type == "interval":
                schedule = BotScheduleConfig(type="interval", hours=config.get("schedule_hours", 6))
            elif schedule_type == "cron":
                schedule = BotScheduleConfig(
                    type="cron",
                    hour=config.get("schedule_hour", 0),
                    minute=config.get("schedule_minute", 0),
                )
            else:
                return json.dumps({"error": "schedule_type must be 'interval' or 'cron'"})

            new_config = BotConfig(
                name=bot_name,
                display_name=config.get("display_name", bot_name),
                description=config.get("description", ""),
                model=config.get("model", "default"),
                temperature=config.get("temperature", 0.3),
                max_tokens=config.get("max_tokens", 4096),
                tools=config.get("tools", []),
                prompt=config.get("prompt", ""),
                schedule=schedule,
                requires_approval=config.get("requires_approval", False),
                timeout_minutes=config.get("timeout_minutes", 10),
                is_custom=True,
            )

            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                bot_manager.create_custom_bot(new_config), loop
            )
            result = future.result(timeout=30)
            return json.dumps({"action": "create", "bot_name": bot_name, **result})

        return json.dumps({"error": "Unhandled action"})
    except Exception as e:
        logger.error("manage_bot error: %s", e)
        return json.dumps({"error": f"Bot management failed: {e}"})
