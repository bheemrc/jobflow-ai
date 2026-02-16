"""Hot-reload functionality for bot configuration.

Supports reloading bots.yaml without full process restart.
"""

from __future__ import annotations

import logging
from typing import Any

from app.event_bus import event_bus

logger = logging.getLogger(__name__)


async def reload_bot_config() -> dict:
    """Reload bots.yaml without full process restart.

    Steps:
    1. Re-read and parse bots.yaml
    2. Compare with current config
    3. Update bot_manager's internal config
    4. Re-register with activation router
    5. Emit config_reloaded event
    """
    try:
        from app.bot_config import read_bots_yaml, reload_bots_config as _reload_config
        from app.bot_manager import bot_manager

        # Read fresh YAML
        yaml_text = read_bots_yaml()
        if not yaml_text:
            return {"ok": False, "error": "Could not read bots.yaml"}

        # Reload config singleton (validates YAML + tool references)
        new_config = _reload_config(yaml_text)

        # Get list of bots for comparison
        old_bots = set(bot_manager._bot_states.keys())
        new_bots = set(new_config.bots.keys())

        added = new_bots - old_bots
        removed = old_bots - new_bots
        updated = old_bots & new_bots

        # Update bot_manager's config reference
        bot_manager._bots_config = new_config

        # Handle removed bots
        for name in removed:
            if name in bot_manager._bot_states:
                # Stop if running
                if bot_manager.is_running(name):
                    await bot_manager.stop_bot(name)
                # Remove from state tracking
                bot_manager._bot_states.pop(name, None)
                bot_manager._enabled_bots.discard(name)
                bot_manager._paused_bots.discard(name)
                # Unregister from router
                if bot_manager._router:
                    bot_manager._router.unregister(name)

        # Handle added bots
        for name in added:
            cfg = new_config.bots[name]
            bot_manager._bot_states[name] = {
                "name": name,
                "display_name": cfg.display_name,
                "description": cfg.description,
                "status": "waiting",
                "enabled": True,
                "last_run_at": None,
                "cooldown_until": None,
                "runs_today": 0,
                "max_runs_per_day": cfg.intent.max_runs_per_day,
                "last_activated_by": None,
                "total_runs": 0,
                "config": {
                    "model": cfg.model,
                    "temperature": cfg.temperature,
                    "intent": {
                        "cooldown_minutes": cfg.intent.cooldown_minutes,
                        "max_runs_per_day": cfg.intent.max_runs_per_day,
                        "signal_count": len(cfg.intent.signals),
                    },
                    "heartbeat_hours": cfg.heartbeat_hours,
                    "requires_approval": cfg.requires_approval,
                    "timeout_minutes": cfg.timeout_minutes,
                },
            }
            bot_manager._enabled_bots.add(name)

            # Register with activation router
            if bot_manager._router:
                from app.activation.intent import BotIntent, IntentSignal
                signals = [
                    IntentSignal(name=s.name, filter=s.filter, priority=s.priority)
                    for s in cfg.intent.signals
                ]
                intent = BotIntent(
                    signals=signals,
                    cooldown_minutes=cfg.intent.cooldown_minutes,
                    max_runs_per_day=cfg.intent.max_runs_per_day,
                )
                bot_manager._router.register(name, intent)

        # Handle updated bots (refresh state from new config)
        for name in updated:
            cfg = new_config.bots[name]
            state = bot_manager._bot_states.get(name, {})
            state["display_name"] = cfg.display_name
            state["description"] = cfg.description
            state["max_runs_per_day"] = cfg.intent.max_runs_per_day
            state["config"] = {
                "model": cfg.model,
                "temperature": cfg.temperature,
                "intent": {
                    "cooldown_minutes": cfg.intent.cooldown_minutes,
                    "max_runs_per_day": cfg.intent.max_runs_per_day,
                    "signal_count": len(cfg.intent.signals),
                },
                "heartbeat_hours": cfg.heartbeat_hours,
                "requires_approval": cfg.requires_approval,
                "timeout_minutes": cfg.timeout_minutes,
            }

        # Emit reload event
        await event_bus.publish({
            "type": "config_reloaded",
            "added_bots": list(added),
            "removed_bots": list(removed),
            "updated_bots": list(updated),
            "total_bots": len(new_config.bots),
        })

        logger.info(
            "Bot config hot-reloaded: %d bots total, %d added, %d removed, %d updated",
            len(new_config.bots), len(added), len(removed), len(updated)
        )

        return {
            "ok": True,
            "total_bots": len(new_config.bots),
            "added": list(added),
            "removed": list(removed),
            "updated": list(updated),
        }

    except Exception as e:
        logger.error("Config reload failed: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}


async def trigger_service_reload(reason: str) -> dict:
    """Trigger a graceful service restart to reload configuration.

    Currently uses internal hot-reload. Can be extended to support:
    1. Signal-based (SIGHUP) — if running under supervisor
    2. Subprocess restart — spawn new process, graceful shutdown old
    3. Kubernetes rolling restart — if in K8s
    """
    logger.info("Service reload triggered: %s", reason)

    # Use internal hot-reload (fastest, no downtime)
    result = await reload_bot_config()

    if result.get("ok"):
        await event_bus.publish({
            "type": "service_reloaded",
            "reason": reason,
            "method": "hot_reload",
        })

    return result
