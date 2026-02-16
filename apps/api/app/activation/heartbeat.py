"""Heartbeat monitor — safety net that nudges idle bots.

Single asyncio task that checks every 30 minutes whether any bot has been
silent too long. If so, publishes a heartbeat:bot_idle event (does NOT start
bots directly — the router handles that).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.event_bus import event_bus

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30 * 60  # 30 minutes
STARTUP_GRACE_SECONDS = 10 * 60   # 10 minutes — no nudges right after boot


class HeartbeatMonitor:
    """Watches for idle bots and emits heartbeat:bot_idle events."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._heartbeat_config: dict[str, int] = {}  # bot_name -> heartbeat_hours
        self._started_at: datetime | None = None

    def configure(self, bot_name: str, heartbeat_hours: int) -> None:
        """Register a bot's heartbeat threshold."""
        if heartbeat_hours > 0:
            self._heartbeat_config[bot_name] = heartbeat_hours

    def start(self, get_last_run: callable) -> None:
        """Start the heartbeat background task.

        Args:
            get_last_run: callable(bot_name) -> datetime | None
        """
        self._get_last_run = get_last_run
        self._started_at = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._loop(), name="heartbeat_monitor")
        logger.info("HeartbeatMonitor started (checking every %ds)", CHECK_INTERVAL_SECONDS)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def _loop(self) -> None:
        try:
            # Startup grace period
            await asyncio.sleep(STARTUP_GRACE_SECONDS)

            while True:
                await self._check_all()
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("HeartbeatMonitor crashed: %s", e, exc_info=True)

    async def _check_all(self) -> None:
        now = datetime.now(timezone.utc)

        for bot_name, heartbeat_hours in self._heartbeat_config.items():
            last_run = self._get_last_run(bot_name)
            if last_run is None:
                # Never run — use startup time as baseline
                last_run = self._started_at

            hours_idle = (now - last_run).total_seconds() / 3600
            if hours_idle >= heartbeat_hours:
                logger.info(
                    "Heartbeat: bot %s idle for %.1fh (threshold=%dh), emitting nudge",
                    bot_name, hours_idle, heartbeat_hours,
                )
                await event_bus.publish({
                    "type": "heartbeat:bot_idle",
                    "bot_name": bot_name,
                    "hours_idle": round(hours_idle, 1),
                    "heartbeat_hours": heartbeat_hours,
                })
