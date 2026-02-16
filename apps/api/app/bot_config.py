"""Config-driven bot definitions loaded from bots.yaml.

Mirrors flow_config.py pattern: dataclasses, singleton, hot-reload.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

BOTS_YAML_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bots.yaml")


@dataclass
class BotScheduleConfig:
    type: str  # "interval" or "cron"
    hours: int | None = None
    minutes: int | None = None
    hour: int | None = None
    minute: int | None = None
    day_of_week: str | None = None


@dataclass
class BotTriggerConfig:
    events: list[str] = field(default_factory=list)


@dataclass
class IntentSignalConfig:
    """A single event pattern a bot listens for."""
    name: str
    filter: dict = field(default_factory=dict)
    priority: str = "medium"


@dataclass
class BotIntentConfig:
    """Full activation intent for a bot."""
    signals: list[IntentSignalConfig] = field(default_factory=list)
    cooldown_minutes: int = 120
    max_runs_per_day: int = 6


@dataclass
class BotDNAConfig:
    """DNA system configuration for a bot."""
    enabled: bool = False
    extract_genes: bool = True       # Extract genes from bot output
    inject_genome: bool = True       # Inject genome context into prompts
    seed_genes: list[dict] = field(default_factory=list)  # Initial gene definitions


@dataclass
class BotPulseConfig:
    """Pulse system configuration for a bot."""
    enabled: bool = False
    frequency_minutes: int = 60
    active_hours_start: int = 6
    active_hours_end: int = 22
    max_actions_per_pulse: int = 3
    expression_bias: float = 0.5


@dataclass
class BotConfig:
    name: str
    display_name: str
    description: str
    model: str  # tier key: "fast", "default", "strong"
    temperature: float
    max_tokens: int
    tools: list[str]
    prompt: str
    schedule: BotScheduleConfig
    trigger_on: list[str] = field(default_factory=list)
    requires_approval: bool = False
    approval_type: str = ""
    approval_priority: str = "medium"
    min_tool_calls: int = 0
    max_reflections: int = 0
    quality_criteria: list[str] = field(default_factory=list)
    timeout_minutes: int = 10
    max_concurrent_runs: int = 1
    max_tool_rounds: int = 6
    is_custom: bool = False
    integrations: dict = field(default_factory=dict)  # {telegram: {...}, slack: {...}, ...}
    dna: BotDNAConfig = field(default_factory=BotDNAConfig)
    pulse: BotPulseConfig = field(default_factory=BotPulseConfig)
    intent: BotIntentConfig = field(default_factory=BotIntentConfig)
    enabled: bool = True  # Whether bot starts enabled on server boot
    heartbeat_hours: int = 0  # 0 = no heartbeat monitoring


@dataclass
class BotsFlowConfig:
    bots: dict[str, BotConfig]
    models: dict[str, str]
    defaults: dict[str, int]

    def resolve_model(self, tier: str) -> str:
        return self.models.get(tier, self.models.get("default", "gpt-4o"))

    def get_tools_for_bot(self, bot_name: str) -> list:
        """Resolve tool string names to actual tool objects."""
        from app.tools import TOOL_REGISTRY
        cfg = self.bots.get(bot_name)
        if not cfg:
            return []
        return [TOOL_REGISTRY[t] for t in cfg.tools if t in TOOL_REGISTRY]

    def get_bots_with_trigger(self, event: str) -> list[BotConfig]:
        """Return all bots that should trigger on the given event."""
        return [b for b in self.bots.values() if event in b.trigger_on]

    def add_bot(self, bot_config: BotConfig) -> None:
        """Add a custom bot to the config at runtime."""
        self.bots[bot_config.name] = bot_config

    def remove_bot(self, name: str) -> bool:
        """Remove a bot from config. Returns True if found and removed."""
        if name in self.bots:
            del self.bots[name]
            return True
        return False


def _parse_dna_config(raw: dict | None) -> BotDNAConfig:
    if not raw:
        return BotDNAConfig()
    return BotDNAConfig(
        enabled=raw.get("enabled", False),
        extract_genes=raw.get("extract_genes", True),
        inject_genome=raw.get("inject_genome", True),
        seed_genes=raw.get("seed_genes", []),
    )


def _parse_pulse_config(raw: dict | None) -> BotPulseConfig:
    if not raw:
        return BotPulseConfig()
    return BotPulseConfig(
        enabled=raw.get("enabled", False),
        frequency_minutes=raw.get("frequency_minutes", 60),
        active_hours_start=raw.get("active_hours_start", 6),
        active_hours_end=raw.get("active_hours_end", 22),
        max_actions_per_pulse=raw.get("max_actions_per_pulse", 3),
        expression_bias=raw.get("expression_bias", 0.5),
    )


def _parse_intent_config(raw: dict | None, trigger_on: list[str] | None = None) -> BotIntentConfig:
    """Parse intent config from YAML, or auto-convert legacy trigger_on."""
    if raw:
        signals = []
        for sig_raw in raw.get("signals", []):
            signals.append(IntentSignalConfig(
                name=sig_raw.get("name", ""),
                filter=sig_raw.get("filter", {}),
                priority=sig_raw.get("priority", "medium"),
            ))
        return BotIntentConfig(
            signals=signals,
            cooldown_minutes=raw.get("cooldown_minutes", 120),
            max_runs_per_day=raw.get("max_runs_per_day", 6),
        )

    # Backward compat: auto-convert trigger_on list to intent signals
    if trigger_on:
        signals = [
            IntentSignalConfig(name=evt, priority="medium")
            for evt in trigger_on
        ]
        return BotIntentConfig(signals=signals)

    return BotIntentConfig()


def _parse_schedule(raw: dict) -> BotScheduleConfig:
    return BotScheduleConfig(
        type=raw.get("type", "interval"),
        hours=raw.get("hours"),
        minutes=raw.get("minutes"),
        hour=raw.get("hour"),
        minute=raw.get("minute"),
        day_of_week=raw.get("day_of_week"),
    )


def _parse_bots_config(raw: dict) -> BotsFlowConfig:
    """Parse raw YAML dict into BotsFlowConfig."""
    models = raw.get("models", {"fast": "gpt-4o-mini", "default": "gpt-4o", "strong": "gpt-4o"})
    defaults = raw.get("defaults", {})

    bots: dict[str, BotConfig] = {}
    for name, cfg in raw.get("bots", {}).items():
        schedule_raw = cfg.get("schedule", {"type": "interval", "hours": 6})
        bots[name] = BotConfig(
            name=name,
            display_name=cfg.get("display_name", name),
            description=cfg.get("description", ""),
            model=cfg.get("model", "default"),
            temperature=cfg.get("temperature", 0.5),
            max_tokens=cfg.get("max_tokens", 4096),
            tools=cfg.get("tools", []),
            prompt=cfg.get("prompt", ""),
            schedule=_parse_schedule(schedule_raw),
            trigger_on=cfg.get("trigger_on", []),
            requires_approval=cfg.get("requires_approval", False),
            approval_type=cfg.get("approval_type", ""),
            approval_priority=cfg.get("approval_priority", "medium"),
            min_tool_calls=cfg.get("min_tool_calls", 0),
            max_reflections=cfg.get("max_reflections", 0),
            quality_criteria=cfg.get("quality_criteria", []),
            timeout_minutes=cfg.get("timeout_minutes", defaults.get("timeout_minutes", 10)),
            max_concurrent_runs=cfg.get("max_concurrent_runs", defaults.get("max_concurrent_runs", 1)),
            max_tool_rounds=cfg.get("max_tool_rounds", defaults.get("max_tool_rounds", 6)),
            dna=_parse_dna_config(cfg.get("dna")),
            pulse=_parse_pulse_config(cfg.get("pulse")),
            intent=_parse_intent_config(cfg.get("intent"), cfg.get("trigger_on")),
            enabled=cfg.get("enabled", True),
            heartbeat_hours=cfg.get("heartbeat_hours", 0),
        )

    return BotsFlowConfig(bots=bots, models=models, defaults=defaults)


# Module-level singleton
_bots_config: BotsFlowConfig | None = None


def load_bots_config(yaml_text: str | None = None, path: str = BOTS_YAML_PATH) -> BotsFlowConfig:
    """Load config from YAML text or file path."""
    global _bots_config
    if yaml_text:
        raw = yaml.safe_load(yaml_text)
    else:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)

    _bots_config = _parse_bots_config(raw)
    logger.info("Bots config loaded: %d bots", len(_bots_config.bots))
    return _bots_config


def get_bots_config() -> BotsFlowConfig:
    """Return cached config, loading from disk if needed."""
    global _bots_config
    if _bots_config is None:
        _bots_config = load_bots_config()
    return _bots_config


def reload_bots_config(yaml_text: str) -> BotsFlowConfig:
    """Parse + validate + replace singleton. Raises on invalid YAML."""
    raw = yaml.safe_load(yaml_text)
    if not isinstance(raw, dict):
        raise ValueError("YAML must be a mapping at the top level")
    if "bots" not in raw:
        raise ValueError("YAML must contain a 'bots' key")

    config = _parse_bots_config(raw)

    # Validate all tool references
    from app.tools import TOOL_REGISTRY
    for name, bot_cfg in config.bots.items():
        for tool_name in bot_cfg.tools:
            if tool_name not in TOOL_REGISTRY:
                raise ValueError(f"Bot '{name}' references unknown tool '{tool_name}'")

    global _bots_config
    _bots_config = config
    logger.info("Bots config hot-reloaded: %d bots", len(config.bots))
    return config


def read_bots_yaml() -> str:
    """Read the current bots.yaml from disk."""
    try:
        with open(BOTS_YAML_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def save_bots_yaml(yaml_text: str) -> None:
    """Persist YAML text to disk."""
    with open(BOTS_YAML_PATH, "w") as f:
        f.write(yaml_text)
