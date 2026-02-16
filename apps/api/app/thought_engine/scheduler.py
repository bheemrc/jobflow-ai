"""Scheduled trigger runner — background loop for cron-based agent posts."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.db import get_thought_triggers, update_trigger_last_fired
from app.event_bus import event_bus

logger = logging.getLogger("app.thought_engine")

_scheduler_task: asyncio.Task | None = None


def _parse_cron_field(field: str, current: int, max_val: int) -> bool:
    """Check if a cron field matches the current value. Supports * and integers."""
    if field == "*":
        return True
    try:
        return int(field) == current
    except ValueError:
        return False


def _cron_matches_now(cron_expr: str) -> bool:
    """Check if a cron expression (minute hour day month weekday) matches now (UTC)."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    now = datetime.now(timezone.utc)
    minute_ok = _parse_cron_field(parts[0], now.minute, 59)
    hour_ok = _parse_cron_field(parts[1], now.hour, 23)
    dom_ok = _parse_cron_field(parts[2], now.day, 31)
    month_ok = _parse_cron_field(parts[3], now.month, 12)
    cron_dow = (now.weekday() + 1) % 7
    dow_ok = _parse_cron_field(parts[4], cron_dow, 6)
    return minute_ok and hour_ok and dom_ok and month_ok and dow_ok


async def _run_scheduled_triggers() -> None:
    """Background loop: check scheduled triggers every 60 seconds."""
    while True:
        try:
            await asyncio.sleep(60)
            triggers = await get_thought_triggers(enabled_only=True)
            now = datetime.now(timezone.utc)

            for trigger in triggers:
                if trigger.get("trigger_type") != "schedule":
                    continue

                config = trigger.get("trigger_config", {})
                schedule = config.get("schedule", "")
                if not schedule or not _cron_matches_now(schedule):
                    continue

                last_fired = trigger.get("last_triggered_at")
                cooldown = trigger.get("cooldown_minutes", 720)
                if last_fired:
                    try:
                        last_dt = datetime.fromisoformat(last_fired) if isinstance(last_fired, str) else last_fired
                        if now - last_dt < timedelta(minutes=cooldown):
                            continue
                    except Exception:
                        pass

                agent = trigger["agent"]
                prompt_template = trigger["prompt_template"]

                # Lazy import to avoid circular dependency
                from .event_handlers import _generate_thought

                post = await _generate_thought(agent, prompt_template, "scheduled", {})
                if post:
                    await update_trigger_last_fired(trigger["id"])
                    await event_bus.publish({
                        "type": "timeline_post",
                        "post": post,
                        "source": "thought_engine",
                    })
                    logger.info("Scheduled post from %s", agent)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Scheduled trigger loop error: %s", e)


async def start_scheduler() -> None:
    """Start the background scheduled trigger runner."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_run_scheduled_triggers())
        logger.info("Scheduled trigger runner started")


async def stop_scheduler() -> None:
    """Stop the background scheduled trigger runner."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
        logger.info("Scheduled trigger runner stopped")
