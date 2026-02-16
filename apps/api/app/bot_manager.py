"""Bot lifecycle manager — event-driven activation, start/stop/pause, and run tracking.

Uses the activation router (intent matching + cooldown) instead of APScheduler.
Bots wake up when there's a reason to act, and sleep when there isn't.

Tracks active runs as asyncio.Tasks. Enforces concurrency and timeouts.
Emits lifecycle events via EventBus.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.bot_config import BotConfig, BotsFlowConfig, get_bots_config, load_bots_config
from app.bot_engine import execute_bot, execute_bot_with_retry
from app.event_bus import event_bus

logger = logging.getLogger(__name__)


class BotManager:
    """Orchestrates bot lifecycle: event-driven activation, execution, and state management."""

    def __init__(self) -> None:
        self._bots_config: BotsFlowConfig | None = None
        self._active_runs: dict[str, asyncio.Task] = {}
        self._bot_states: dict[str, dict] = {}
        self._paused_bots: set[str] = set()
        self._enabled_bots: set[str] = set()
        self._initialized = False
        self._run_lock = asyncio.Lock()  # Prevent race conditions on start
        self._router: Any = None  # ActivationRouter
        self._heartbeat: Any = None  # HeartbeatMonitor
        self._pulse_runner: Any = None  # PulseRunner

    async def initialize(self) -> None:
        """Load config, set up activation router + heartbeat. Called during app lifespan."""
        self._bots_config = load_bots_config()

        # Initialize bot states
        for name, cfg in self._bots_config.bots.items():
            self._bot_states[name] = {
                "name": name,
                "display_name": cfg.display_name,
                "description": cfg.description,
                "status": "waiting" if cfg.enabled else "disabled",
                "enabled": cfg.enabled,
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
            if cfg.enabled:
                self._enabled_bots.add(name)

        # Seed DB bot records
        from app.db import upsert_bot_record
        for name, cfg in self._bots_config.bots.items():
            await upsert_bot_record(name, cfg.display_name, self._bot_states[name]["config"])

        # Set up activation router
        await self._setup_activation()

        self._initialized = True
        logger.info("BotManager initialized with %d bots (event-driven)", len(self._bots_config.bots))

        # Publish initial state
        await self._emit_full_state()

    async def _setup_activation(self) -> None:
        """Configure activation router, heartbeat monitor, and pulse runner."""
        from app.activation.router import ActivationRouter
        from app.activation.heartbeat import HeartbeatMonitor
        from app.activation.intent import BotIntent, IntentSignal

        # Build router
        self._router = ActivationRouter()
        self._heartbeat = HeartbeatMonitor()

        for name, cfg in self._bots_config.bots.items():
            # Register intent signals
            signals = [
                IntentSignal(
                    name=s.name,
                    filter=s.filter,
                    priority=s.priority,
                )
                for s in cfg.intent.signals
            ]
            intent = BotIntent(
                signals=signals,
                cooldown_minutes=cfg.intent.cooldown_minutes,
                max_runs_per_day=cfg.intent.max_runs_per_day,
            )
            self._router.register(name, intent)

            # Register heartbeat
            if cfg.heartbeat_hours > 0:
                self._heartbeat.configure(name, cfg.heartbeat_hours)

        # Start router + heartbeat
        self._router.start()
        self._heartbeat.start(self._get_last_run_time)

        # Start pulse runner for DNA-enabled bots
        try:
            from app.dna.pulse_scheduler import PulseRunner
            self._pulse_runner = PulseRunner()
            for name, cfg in self._bots_config.bots.items():
                if cfg.pulse.enabled:
                    self._pulse_runner.configure(
                        name, cfg.pulse.active_hours_start, cfg.pulse.active_hours_end
                    )
            self._pulse_runner.start()

            # Seed genes from config
            from app.dna.pulse_scheduler import seed_genes_for_bot
            for name, cfg in self._bots_config.bots.items():
                if cfg.dna.enabled and cfg.dna.seed_genes:
                    await seed_genes_for_bot(name, cfg.dna.seed_genes)
        except Exception as e:
            logger.warning("PulseRunner setup failed (DNA features unavailable): %s", e)

        logger.info("Activation router started with %d bot intents", len(self._bots_config.bots))

    def _get_last_run_time(self, bot_name: str) -> datetime | None:
        """Get the last run time for a bot (used by heartbeat monitor)."""
        state = self._bot_states.get(bot_name)
        if not state or not state.get("last_run_at"):
            return None
        last = state["last_run_at"]
        if isinstance(last, str):
            return datetime.fromisoformat(last)
        return last

    # ── Public API ──

    async def start_bot(self, bot_name: str, trigger_type: str = "manual", context: str | None = None, user_id: str = "") -> dict:
        """Start a bot run. Returns immediately with run info."""
        if not self._bots_config:
            return {"error": "BotManager not initialized"}

        cfg = self._bots_config.bots.get(bot_name)
        if not cfg:
            return {"error": f"Unknown bot: {bot_name}"}

        if bot_name in self._paused_bots:
            return {"error": f"Bot {bot_name} is paused", "status": "paused"}

        if bot_name not in self._enabled_bots:
            return {"error": f"Bot {bot_name} is disabled", "status": "disabled"}

        # Use lock to prevent race between router and manual trigger
        async with self._run_lock:
            # Check concurrency
            if bot_name in self._active_runs and not self._active_runs[bot_name].done():
                return {"error": f"Bot {bot_name} is already running", "status": "already_running"}

            # Create and track the async task
            task = asyncio.create_task(
                self._run_bot_with_timeout(cfg, trigger_type, context=context, user_id=user_id),
                name=f"bot_run_{bot_name}",
            )
            self._active_runs[bot_name] = task

        # Update state
        self._bot_states[bot_name]["status"] = "running"
        self._bot_states[bot_name]["last_activated_by"] = trigger_type
        await event_bus.publish({
            "type": "bot_state_change",
            "bot_name": bot_name,
            "status": "running",
            "trigger_type": trigger_type,
        })

        return {"ok": True, "bot_name": bot_name, "status": "running", "trigger_type": trigger_type}

    async def _run_bot_with_timeout(self, cfg: BotConfig, trigger_type: str, context: str | None = None, user_id: str = "") -> dict:
        """Run a bot with timeout enforcement."""
        try:
            result = await asyncio.wait_for(
                execute_bot_with_retry(cfg, self._bots_config, trigger_type=trigger_type, context=context, user_id=user_id),
                timeout=cfg.timeout_minutes * 60,
            )

            # Update state on completion
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            self._bot_states[cfg.name]["status"] = "waiting"
            self._bot_states[cfg.name]["last_run_at"] = now_iso
            self._bot_states[cfg.name]["total_runs"] = self._bot_states[cfg.name].get("total_runs", 0) + 1

            # Update cooldown info from router
            if self._router:
                cd_until = self._router.cooldown.get_cooldown_until(
                    cfg.name, cfg.intent.cooldown_minutes
                )
                self._bot_states[cfg.name]["cooldown_until"] = cd_until.isoformat() if cd_until else None
                self._bot_states[cfg.name]["runs_today"] = self._router.cooldown.get_daily_count(cfg.name)

            await event_bus.publish({
                "type": "bot_state_change",
                "bot_name": cfg.name,
                "status": "waiting",
                "last_run_at": now_iso,
                "cooldown_until": self._bot_states[cfg.name].get("cooldown_until"),
                "runs_today": self._bot_states[cfg.name].get("runs_today", 0),
            })

            return result

        except asyncio.TimeoutError:
            logger.error("Bot %s timed out after %d minutes", cfg.name, cfg.timeout_minutes)
            self._bot_states[cfg.name]["status"] = "errored"

            await event_bus.publish({
                "type": "bot_run_error",
                "bot_name": cfg.name,
                "error": f"Timed out after {cfg.timeout_minutes} minutes",
            })
            await event_bus.publish({
                "type": "bot_state_change",
                "bot_name": cfg.name,
                "status": "errored",
            })

            return {"status": "errored", "error": "timeout"}

        except Exception as e:
            logger.error("Bot %s run failed: %s", cfg.name, e, exc_info=True)
            self._bot_states[cfg.name]["status"] = "errored"

            await event_bus.publish({
                "type": "bot_state_change",
                "bot_name": cfg.name,
                "status": "errored",
            })

            return {"status": "errored", "error": str(e)}

        finally:
            # Clean up active run
            self._active_runs.pop(cfg.name, None)

    async def stop_bot(self, bot_name: str) -> dict:
        """Stop a running bot."""
        # Cancel active run if any
        task = self._active_runs.get(bot_name)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        self._active_runs.pop(bot_name, None)
        self._bot_states[bot_name]["status"] = "stopped"
        self._paused_bots.add(bot_name)

        await event_bus.publish({
            "type": "bot_state_change",
            "bot_name": bot_name,
            "status": "stopped",
        })

        return {"ok": True, "bot_name": bot_name, "status": "stopped"}

    async def pause_bot(self, bot_name: str) -> dict:
        """Pause a bot (current run continues if active)."""
        self._paused_bots.add(bot_name)

        if bot_name not in self._active_runs or self._active_runs[bot_name].done():
            self._bot_states[bot_name]["status"] = "paused"

        await event_bus.publish({
            "type": "bot_state_change",
            "bot_name": bot_name,
            "status": "paused",
        })

        return {"ok": True, "bot_name": bot_name, "status": "paused"}

    async def resume_bot(self, bot_name: str) -> dict:
        """Resume a paused bot."""
        self._paused_bots.discard(bot_name)

        if bot_name not in self._active_runs or self._active_runs[bot_name].done():
            self._bot_states[bot_name]["status"] = "waiting"

        await event_bus.publish({
            "type": "bot_state_change",
            "bot_name": bot_name,
            "status": "waiting",
        })

        return {"ok": True, "bot_name": bot_name, "status": "waiting"}

    async def set_enabled(self, bot_name: str, enabled: bool) -> dict:
        """Enable or disable a bot entirely."""
        if enabled:
            self._enabled_bots.add(bot_name)
            self._paused_bots.discard(bot_name)
            self._bot_states[bot_name]["status"] = "waiting"
            self._bot_states[bot_name]["enabled"] = True
        else:
            self._enabled_bots.discard(bot_name)
            await self.stop_bot(bot_name)
            self._bot_states[bot_name]["status"] = "disabled"
            self._bot_states[bot_name]["enabled"] = False

        await event_bus.publish({
            "type": "bot_state_change",
            "bot_name": bot_name,
            "status": self._bot_states[bot_name]["status"],
            "enabled": enabled,
        })

        return {"ok": True, "bot_name": bot_name, "enabled": enabled}

    async def update_schedule(self, bot_name: str, schedule_config: dict) -> dict:
        """Update a bot's intent configuration (backward-compat endpoint name)."""
        if bot_name not in self._bot_states:
            return {"error": f"Unknown bot: {bot_name}"}

        # Accept intent config updates through the schedule endpoint
        self._bot_states[bot_name]["config"]["intent"] = schedule_config
        return {"ok": True, "bot_name": bot_name}

    async def update_config(self, bot_name: str, config_update: dict) -> dict:
        """Update a bot's configuration parameters."""
        if bot_name not in self._bot_states:
            return {"error": f"Unknown bot: {bot_name}"}

        for key, value in config_update.items():
            if key in self._bot_states[bot_name]["config"]:
                self._bot_states[bot_name]["config"][key] = value
            elif key == "integrations":
                self._bot_states[bot_name]["integrations"] = value

        return {"ok": True, "bot_name": bot_name}

    async def start_all(self) -> dict:
        """Start all enabled bots."""
        results = {}
        for name in self._enabled_bots:
            if name not in self._paused_bots:
                results[name] = await self.start_bot(name, trigger_type="manual")
        return results

    async def stop_all(self) -> dict:
        """Stop all running bots."""
        results = {}
        for name in list(self._active_runs.keys()):
            results[name] = await self.stop_bot(name)
        return results

    # ── Custom bot creation ──

    async def create_custom_bot(self, bot_config: BotConfig) -> dict:
        """Register a custom bot at runtime."""
        if bot_config.name in self._bot_states:
            return {"error": f"Bot '{bot_config.name}' already exists"}

        # Add to config singleton
        if self._bots_config:
            self._bots_config.add_bot(bot_config)

        # Initialize state
        self._bot_states[bot_config.name] = {
            "name": bot_config.name,
            "display_name": bot_config.display_name,
            "description": bot_config.description,
            "status": "waiting",
            "enabled": True,
            "last_run_at": None,
            "cooldown_until": None,
            "runs_today": 0,
            "max_runs_per_day": bot_config.intent.max_runs_per_day,
            "last_activated_by": None,
            "total_runs": 0,
            "is_custom": True,
            "integrations": bot_config.integrations,
            "config": {
                "model": bot_config.model,
                "temperature": bot_config.temperature,
                "intent": {
                    "cooldown_minutes": bot_config.intent.cooldown_minutes,
                    "max_runs_per_day": bot_config.intent.max_runs_per_day,
                    "signal_count": len(bot_config.intent.signals),
                },
                "heartbeat_hours": bot_config.heartbeat_hours,
                "requires_approval": bot_config.requires_approval,
                "timeout_minutes": bot_config.timeout_minutes,
            },
        }
        self._enabled_bots.add(bot_config.name)

        # Seed DB
        from app.db import upsert_bot_record
        await upsert_bot_record(bot_config.name, bot_config.display_name,
                                self._bot_states[bot_config.name]["config"])

        # Register with activation router
        if self._router:
            from app.activation.intent import BotIntent, IntentSignal
            signals = [
                IntentSignal(name=s.name, filter=s.filter, priority=s.priority)
                for s in bot_config.intent.signals
            ]
            intent = BotIntent(
                signals=signals,
                cooldown_minutes=bot_config.intent.cooldown_minutes,
                max_runs_per_day=bot_config.intent.max_runs_per_day,
            )
            self._router.register(bot_config.name, intent)

        if self._heartbeat and bot_config.heartbeat_hours > 0:
            self._heartbeat.configure(bot_config.name, bot_config.heartbeat_hours)

        # Emit state change
        await self._emit_full_state()

        logger.info("Custom bot created: %s", bot_config.name)
        return {"ok": True, "bot_name": bot_config.name, "status": "waiting"}

    async def delete_custom_bot(self, bot_name: str) -> dict:
        """Delete a custom bot."""
        state = self._bot_states.get(bot_name)
        if not state:
            return {"error": f"Bot '{bot_name}' not found"}
        if not state.get("is_custom"):
            return {"error": f"Bot '{bot_name}' is a built-in bot and cannot be deleted"}

        # Stop if running
        await self.stop_bot(bot_name)

        # Unregister from router
        if self._router:
            self._router.unregister(bot_name)

        # Remove from all tracking
        self._bot_states.pop(bot_name, None)
        self._enabled_bots.discard(bot_name)
        self._paused_bots.discard(bot_name)

        if self._bots_config:
            self._bots_config.remove_bot(bot_name)

        await self._emit_full_state()
        logger.info("Custom bot deleted: %s", bot_name)
        return {"ok": True, "bot_name": bot_name}

    # ── Event handling ──

    async def handle_event(self, event_name: str, event_context: dict | None = None) -> None:
        """Publish an event to the event bus for the router to process.

        Also forwards to thought engine for timeline posts.
        """
        # Publish to event bus — the activation router will pick it up
        event = {"type": event_name}
        if event_context:
            event.update(event_context)
        await event_bus.publish(event)

        # Also trigger thought engine for timeline posts
        try:
            from app.thought_engine import handle_event as thought_handle_event
            await thought_handle_event(event_name, event_context)
        except Exception as e:
            logger.debug("Thought engine event handling failed for '%s': %s", event_name, e)

    # ── State queries ──

    def get_all_states(self) -> list[dict]:
        """Get current state of all bots."""
        # Update cooldown info before returning
        if self._router:
            for name, state in self._bot_states.items():
                cfg = self._bots_config.bots.get(name) if self._bots_config else None
                if cfg:
                    cd_until = self._router.cooldown.get_cooldown_until(
                        name, cfg.intent.cooldown_minutes
                    )
                    state["cooldown_until"] = cd_until.isoformat() if cd_until else None
                    state["runs_today"] = self._router.cooldown.get_daily_count(name)
        return list(self._bot_states.values())

    def get_bot_state(self, bot_name: str) -> dict | None:
        return self._bot_states.get(bot_name)

    def is_running(self, bot_name: str) -> bool:
        task = self._active_runs.get(bot_name)
        return task is not None and not task.done()

    def running_count(self) -> int:
        return sum(1 for t in self._active_runs.values() if not t.done())

    def get_scheduler_status(self) -> dict:
        """Return activation system health info for diagnostics."""
        router_running = self._router is not None and self._router._task is not None
        heartbeat_running = self._heartbeat is not None and self._heartbeat._task is not None
        pulse_running = self._pulse_runner is not None

        return {
            "running": router_running,
            "type": "event-driven",
            "router_active": router_running,
            "heartbeat_active": heartbeat_running,
            "pulse_active": pulse_running,
            "registered_intents": len(self._router._intents) if self._router else 0,
        }

    async def _emit_full_state(self) -> None:
        """Publish full bot state snapshot."""
        await event_bus.publish({
            "type": "bots_state",
            "bots": self.get_all_states(),
        })

    # ── Config Reload ──

    async def reload_config(self) -> dict:
        """Reload bots.yaml without full process restart.

        Delegates to the group_chat.reload module.
        """
        try:
            from app.group_chat.reload import reload_bot_config
            result = await reload_bot_config()
            return result
        except Exception as e:
            logger.error("Config reload failed: %s", e)
            return {"ok": False, "error": str(e)}

    # ── Shutdown ──

    async def shutdown(self) -> None:
        """Clean shutdown: cancel all runs, stop router + heartbeat."""
        logger.info("BotManager shutting down...")

        # Cancel all active runs
        for name, task in self._active_runs.items():
            if not task.done():
                task.cancel()

        # Wait for cancellations
        if self._active_runs:
            await asyncio.gather(
                *self._active_runs.values(),
                return_exceptions=True,
            )

        # Stop activation router
        if self._router:
            await self._router.stop()

        # Stop heartbeat
        if self._heartbeat:
            await self._heartbeat.stop()

        # Stop pulse runner
        if self._pulse_runner:
            try:
                await self._pulse_runner.stop()
            except Exception:
                pass

        logger.info("BotManager shutdown complete")


# Module-level singleton
bot_manager = BotManager()
