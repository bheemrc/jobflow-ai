"""Config-driven flow configuration loaded from YAML.

Provides AgentConfig, FlowConfig, and a module-level singleton with hot-reload.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

FLOWS_YAML_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flows.yaml")


@dataclass
class AgentConfig:
    name: str
    display_name: str
    model: str  # tier key: "fast", "default", "strong"
    temperature: float
    max_tokens: int
    tools: list[str]
    prompt: str
    is_specialist: bool = True
    requires_approval: bool = False
    approval_type: str = ""
    approval_priority: str = "medium"
    min_tool_calls: int = 0
    max_reflections: int = 0
    quality_criteria: list[str] = field(default_factory=list)


@dataclass
class RoutingConfig:
    coach_model: str = "fast"
    coach_temperature: float = 0.3
    coach_max_tokens: int = 512
    max_parallel: int = 3
    rules: str = ""
    examples: list[dict] = field(default_factory=list)
    fallbacks: list[dict] = field(default_factory=list)


@dataclass
class FlowConfig:
    agents: dict[str, AgentConfig]
    routing: RoutingConfig
    models: dict[str, str]
    shared: dict[str, str]

    @property
    def specialist_agents(self) -> set[str]:
        return {name for name, cfg in self.agents.items() if cfg.is_specialist}

    @property
    def valid_agents(self) -> set[str]:
        return set(self.agents.keys())

    def resolve_model(self, tier: str) -> str:
        return self.models.get(tier, self.models.get("default", "gpt-4o"))

    def get_coach_prompt(self) -> str:
        """Build the coach routing prompt from config rules + examples."""
        parts = [
            "You are an AI Career Coach router. Your job is to quickly understand what the user needs and route them to the right specialist agents.",
            "",
            "## CRITICAL: You are a ROUTER, not an advisor.",
            "- Do NOT give detailed advice yourself. That's what the specialist agents do.",
            "- Keep your response to 1-2 SHORT sentences acknowledging the request.",
            "- Always end with the routing decision.",
            "",
            "## Routing Rules",
            "Look at the conversation and decide which specialist(s) to invoke. You can route to MULTIPLE agents when the request spans multiple domains — they run in parallel.",
            "",
            self.routing.rules.strip() if self.routing.rules else "",
            "",
            "## Multi-Agent Routing",
            "Route to MULTIPLE agents (comma-separated) when the request naturally spans domains.",
            "Route to a SINGLE agent when the request is focused.",
            f"NEVER route to more than {self.routing.max_parallel} agents at once. Pick the most relevant ones.",
            "If user has no resume uploaded and needs one → respond",
            "If user asks about their resume (summary, skills, experience, profile) → job_intake (it has resume reading tools)",
            "If user asks 'what should I focus on' or general career advice → job_intake (it can analyze their profile)",
            "",
            "## Context Extraction",
            "From the conversation, extract any mentioned company name and role:",
            "[COMPANY: name]",
            "[ROLE: title]",
            "These MUST come before the routing line when present.",
            "",
            "## Routing Format",
            "End your response with ONE routing line (single or comma-separated):",
            "[ROUTE: leetcode_coach]",
            "[ROUTE: resume_tailor, interview_prep]",
            "",
        ]

        if self.routing.examples:
            parts.append("## Examples")
            parts.append("")
            for ex in self.routing.examples:
                parts.append(f'User: "{ex["input"]}"')
                parts.append(f'→ [ROUTE: {ex["route"]}]')
                parts.append("")

        return "\n".join(parts)

    def get_tools_for_agent(self, agent_name: str) -> list:
        """Resolve tool string names to actual tool objects."""
        from app.tools import TOOL_REGISTRY
        cfg = self.agents.get(agent_name)
        if not cfg:
            return []
        return [TOOL_REGISTRY[t] for t in cfg.tools if t in TOOL_REGISTRY]


def _parse_config(raw: dict) -> FlowConfig:
    """Parse raw YAML dict into FlowConfig."""
    models = raw.get("models", {"fast": "gpt-4o-mini", "default": "gpt-4o", "strong": "gpt-4o"})
    shared = raw.get("shared", {})
    tone = shared.get("tone", "")
    depth = shared.get("depth", "")

    agents: dict[str, AgentConfig] = {}
    for name, cfg in raw.get("agents", {}).items():
        is_specialist = cfg.get("is_specialist", True)
        prompt_text = cfg.get("prompt", "")
        # Append shared tone + depth to specialist prompts
        if is_specialist and prompt_text:
            prompt_text = prompt_text.rstrip() + "\n\n" + tone.strip() + "\n\n" + depth.strip()

        agents[name] = AgentConfig(
            name=name,
            display_name=cfg.get("display_name", name),
            model=cfg.get("model", "default"),
            temperature=cfg.get("temperature", 0.5),
            max_tokens=cfg.get("max_tokens", 2048),
            tools=cfg.get("tools", []),
            prompt=prompt_text,
            is_specialist=is_specialist,
            requires_approval=cfg.get("requires_approval", False),
            approval_type=cfg.get("approval_type", ""),
            approval_priority=cfg.get("approval_priority", "medium"),
            min_tool_calls=cfg.get("min_tool_calls", 0),
            max_reflections=cfg.get("max_reflections", 0),
            quality_criteria=cfg.get("quality_criteria", []),
        )

    routing_raw = raw.get("routing", {})
    routing = RoutingConfig(
        coach_model=routing_raw.get("coach_model", "fast"),
        coach_temperature=routing_raw.get("coach_temperature", 0.3),
        coach_max_tokens=routing_raw.get("coach_max_tokens", 512),
        max_parallel=routing_raw.get("max_parallel", 3),
        rules=routing_raw.get("rules", ""),
        examples=routing_raw.get("examples", []),
        fallbacks=routing_raw.get("fallbacks", []),
    )

    return FlowConfig(agents=agents, routing=routing, models=models, shared=shared)


# Module-level singleton
_config: FlowConfig | None = None


def load_flow_config(yaml_text: str | None = None, path: str = FLOWS_YAML_PATH) -> FlowConfig:
    """Load config from YAML text or file path."""
    global _config
    if yaml_text:
        raw = yaml.safe_load(yaml_text)
    else:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)

    _config = _parse_config(raw)
    logger.info(
        "Flow config loaded: %d agents (%s specialists)",
        len(_config.agents),
        len(_config.specialist_agents),
    )
    return _config


def get_flow_config() -> FlowConfig:
    """Return cached config, loading from disk if needed."""
    global _config
    if _config is None:
        _config = load_flow_config()
    return _config


def reload_config(yaml_text: str) -> FlowConfig:
    """Parse + validate + replace singleton. Raises on invalid YAML."""
    raw = yaml.safe_load(yaml_text)
    if not isinstance(raw, dict):
        raise ValueError("YAML must be a mapping at the top level")
    if "agents" not in raw:
        raise ValueError("YAML must contain an 'agents' key")

    config = _parse_config(raw)

    # Validate all tool references
    from app.tools import TOOL_REGISTRY
    for name, agent_cfg in config.agents.items():
        for tool_name in agent_cfg.tools:
            if tool_name not in TOOL_REGISTRY:
                raise ValueError(f"Agent '{name}' references unknown tool '{tool_name}'")

    global _config
    _config = config
    logger.info("Flow config hot-reloaded: %d agents", len(config.agents))
    return config


def read_flows_yaml() -> str:
    """Read the current flows.yaml from disk."""
    try:
        with open(FLOWS_YAML_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def save_flows_yaml(yaml_text: str) -> None:
    """Persist YAML text to disk."""
    with open(FLOWS_YAML_PATH, "w") as f:
        f.write(yaml_text)
