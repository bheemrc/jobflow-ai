"""Pulse runner — adaptive asyncio task replacing APScheduler interval jobs.

Runs pulse cycles for DNA-enabled bots with adaptive frequency:
- 5min if recent events
- 15min if quiet
- 30min if very quiet
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PulseRunner:
    """Single asyncio task running pulse cycles for all DNA-enabled bots."""

    # Adaptive intervals (seconds)
    FREQ_ACTIVE = 5 * 60    # 5 min when recent activity
    FREQ_QUIET = 15 * 60    # 15 min when quiet
    FREQ_VERY_QUIET = 30 * 60  # 30 min when very quiet

    # Activity thresholds (seconds since last notify)
    QUIET_AFTER = 15 * 60
    VERY_QUIET_AFTER = 60 * 60

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._bots: dict[str, tuple[int, int]] = {}  # bot_name -> (active_start, active_end)
        self._last_activity: float = time.monotonic()

    def configure(self, bot_name: str, active_hours_start: int, active_hours_end: int) -> None:
        """Register a DNA-enabled bot for pulse cycles."""
        self._bots[bot_name] = (active_hours_start, active_hours_end)

    def notify_activity(self) -> None:
        """Called when events flow through the system — speeds up pulse frequency."""
        self._last_activity = time.monotonic()

    def start(self) -> None:
        if not self._bots:
            logger.info("PulseRunner: no DNA-enabled bots, not starting")
            return
        self._task = asyncio.create_task(self._loop(), name="pulse_runner")
        logger.info("PulseRunner started for %d bots", len(self._bots))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    def _current_interval(self) -> float:
        elapsed = time.monotonic() - self._last_activity
        if elapsed < self.QUIET_AFTER:
            return self.FREQ_ACTIVE
        elif elapsed < self.VERY_QUIET_AFTER:
            return self.FREQ_QUIET
        return self.FREQ_VERY_QUIET

    async def _loop(self) -> None:
        try:
            while True:
                interval = self._current_interval()
                await asyncio.sleep(interval)
                await self._run_all()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("PulseRunner crashed: %s", e, exc_info=True)

    async def _run_all(self) -> None:
        now = datetime.now(timezone.utc)
        current_hour = now.hour

        for bot_name, (active_start, active_end) in self._bots.items():
            if not _in_active_hours(current_hour, active_start, active_end):
                continue

            try:
                from app.dna.pulse import run_pulse
                user_ids = await _get_all_user_ids()
                if not user_ids:
                    user_ids = [""]
                for uid in user_ids:
                    await run_pulse(bot_name, uid)
            except Exception as e:
                logger.error("Pulse execution failed for %s: %s", bot_name, e)


def _in_active_hours(current_hour: int, start: int, end: int) -> bool:
    if start <= end:
        return start <= current_hour < end
    # Wrapped range: e.g. 22-6
    return current_hour >= start or current_hour < end


async def _get_all_user_ids() -> list[str]:
    """Get all known user IDs from existing data."""
    try:
        from app.db import get_conn
        async with get_conn() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT user_id FROM timeline_posts
                WHERE user_id != '' LIMIT 20
            """)
            return [r["user_id"] for r in rows]
    except Exception:
        return []


async def seed_genes_for_bot(agent: str, seed_genes: list[dict]) -> None:
    """Seed initial genes from YAML config if the agent has no genes yet.

    Seeds for ALL known users so genes are visible regardless of who's logged in.
    """
    if not seed_genes:
        return

    try:
        from app.dna import db as dna_db
        from app.dna.models import DECAY_RATES

        user_ids = await _get_all_user_ids()
        if not user_ids:
            user_ids = [""]

        for uid in user_ids:
            existing = await dna_db.get_genome(agent, uid)
            if existing:
                continue

            for seed in seed_genes:
                if not isinstance(seed, dict) or not seed.get("name"):
                    continue
                gene_type = seed.get("type", "FACT")
                await dna_db.create_gene(
                    agent=agent,
                    gene_type=gene_type,
                    name=seed["name"],
                    description=seed.get("description", ""),
                    confidence=seed.get("confidence", 0.5),
                    decay_rate=DECAY_RATES.get(gene_type, 0.03),
                    source="seed",
                    tags=seed.get("tags", []),
                    user_id=uid,
                )

            logger.info("Seeded %d genes for %s (user=%s)", len(seed_genes), agent, uid[:20] if uid else "default")

    except Exception as e:
        logger.warning("Failed to seed genes for %s: %s", agent, e)


# Legacy compat — no-op since bot_manager now starts PulseRunner
async def initialize_pulse_scheduler() -> None:
    """No-op for backward compatibility. PulseRunner is started by bot_manager."""
    logger.info("initialize_pulse_scheduler() called — pulse is now managed by bot_manager")
