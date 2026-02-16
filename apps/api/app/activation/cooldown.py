"""Cooldown guard — rate-limits bot activations.

Tracks per-bot last activation timestamp and daily run counts.
High-priority events get half the cooldown period.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class CooldownGuard:
    """Per-bot activation rate limiter."""

    def __init__(self) -> None:
        self._last_activation: dict[str, datetime] = {}  # bot_name -> last activation UTC
        self._daily_counts: dict[str, int] = {}  # bot_name -> runs today
        self._last_reset_date: str = ""  # YYYY-MM-DD of last daily reset

    def can_activate(
        self,
        bot_name: str,
        cooldown_minutes: int,
        max_runs_per_day: int,
        priority: str = "medium",
    ) -> bool:
        """Check if a bot can be activated now.

        High priority events use half the cooldown period.
        """
        self._maybe_reset_daily()

        now = datetime.now(timezone.utc)

        # Check daily cap
        daily = self._daily_counts.get(bot_name, 0)
        if daily >= max_runs_per_day:
            logger.debug("Bot %s hit daily cap (%d/%d)", bot_name, daily, max_runs_per_day)
            return False

        # Check cooldown (high priority = half cooldown)
        last = self._last_activation.get(bot_name)
        if last:
            effective_cooldown = cooldown_minutes
            if priority == "high":
                effective_cooldown = cooldown_minutes // 2
            elapsed_minutes = (now - last).total_seconds() / 60
            if elapsed_minutes < effective_cooldown:
                logger.debug(
                    "Bot %s in cooldown (%.1f/%.0f min, priority=%s)",
                    bot_name, elapsed_minutes, effective_cooldown, priority,
                )
                return False

        return True

    def record_activation(self, bot_name: str) -> None:
        """Record that a bot was activated."""
        self._maybe_reset_daily()
        self._last_activation[bot_name] = datetime.now(timezone.utc)
        self._daily_counts[bot_name] = self._daily_counts.get(bot_name, 0) + 1

    def get_cooldown_until(self, bot_name: str, cooldown_minutes: int) -> datetime | None:
        """Return when the cooldown expires, or None if not in cooldown."""
        last = self._last_activation.get(bot_name)
        if not last:
            return None
        from datetime import timedelta
        expires = last + timedelta(minutes=cooldown_minutes)
        now = datetime.now(timezone.utc)
        if expires > now:
            return expires
        return None

    def get_daily_count(self, bot_name: str) -> int:
        self._maybe_reset_daily()
        return self._daily_counts.get(bot_name, 0)

    def get_last_activation(self, bot_name: str) -> datetime | None:
        return self._last_activation.get(bot_name)

    def _maybe_reset_daily(self) -> None:
        """Reset daily counts at midnight UTC."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._daily_counts.clear()
            self._last_reset_date = today
