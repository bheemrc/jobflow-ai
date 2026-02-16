"""Activation router — central nervous system for event-driven bot activation.

Subscribes to the event bus and for each event:
1. IntentMatcher.match(event) → find bots whose intent signals match
2. CooldownGuard.check() → enforce rate limits
3. bot_manager.start_bot() → activate the bot

Filters out meta events to prevent feedback loops.
"""

from __future__ import annotations

import asyncio
import logging

from app.activation.cooldown import CooldownGuard
from app.activation.intent import BotIntent, IntentMatcher
from app.event_bus import event_bus

logger = logging.getLogger(__name__)

# Events that should never trigger bot activation (prevent loops)
META_EVENT_TYPES = frozenset({
    "bot_state_change",
    "bot_log",
    "heartbeat",
    "bots_state",
    "bot_run_start",
    "bot_run_retry",
})


class ActivationRouter:
    """Consumes events from the bus and activates matching bots."""

    def __init__(self) -> None:
        self.matcher = IntentMatcher()
        self.cooldown = CooldownGuard()
        self._task: asyncio.Task | None = None
        self._intents: dict[str, BotIntent] = {}  # bot_name -> BotIntent (for cooldown lookup)

    def register(self, bot_name: str, intent: BotIntent) -> None:
        self.matcher.register(bot_name, intent)
        self._intents[bot_name] = intent

    def unregister(self, bot_name: str) -> None:
        self.matcher.unregister(bot_name)
        self._intents.pop(bot_name, None)

    def start(self) -> None:
        self._task = asyncio.create_task(self._consume_loop(), name="activation_router")
        logger.info("ActivationRouter started")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def _consume_loop(self) -> None:
        try:
            async for event in event_bus.subscribe(include_heartbeats=False):
                event_type = event.get("type", "")

                # Skip meta events to prevent feedback loops
                if event_type in META_EVENT_TYPES:
                    continue

                matches = self.matcher.match(event)
                if not matches:
                    continue

                for bot_name, priority in matches:
                    await self._try_activate(bot_name, priority, event)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("ActivationRouter crashed: %s", e, exc_info=True)

    async def _try_activate(self, bot_name: str, priority: str, event: dict) -> None:
        """Attempt to activate a bot after cooldown check."""
        intent = self._intents.get(bot_name)
        if not intent:
            return

        if not self.cooldown.can_activate(
            bot_name,
            cooldown_minutes=intent.cooldown_minutes,
            max_runs_per_day=intent.max_runs_per_day,
            priority=priority,
        ):
            return

        # Activate via bot_manager (lazy import to avoid circular)
        try:
            from app.bot_manager import bot_manager

            event_type = event.get("type", "unknown")
            logger.info(
                "Router activating %s (priority=%s, event=%s)",
                bot_name, priority, event_type,
            )
            result = await bot_manager.start_bot(
                bot_name,
                trigger_type=f"event:{event_type}",
            )

            if result.get("ok"):
                self.cooldown.record_activation(bot_name)
        except Exception as e:
            logger.warning("Router failed to activate %s: %s", bot_name, e)
