"""Gene, Mutation, PulseLog, PulseConfig dataclasses + constants.

Every gene has a plain English name and description so users can
understand exactly what each gene represents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ── Gene Types ──

class GeneType(str, Enum):
    FACT = "FACT"         # Verified data point (e.g. "User has 5 years Python experience")
    BELIEF = "BELIEF"     # Learned preference/pattern (e.g. "Prefers remote roles")
    SKILL = "SKILL"       # Capability signal (e.g. "Good at system design questions")
    INSIGHT = "INSIGHT"   # Analysis conclusion (e.g. "FAANG hiring is slowing down")
    GOAL = "GOAL"         # Active objective (e.g. "Find senior backend roles in fintech")
    HUNCH = "HUNCH"       # Low-confidence lead (e.g. "Stripe might be expanding ML team")


# ── Decay Rates (confidence loss per day of inactivity) ──

DECAY_RATES: dict[str, float] = {
    "FACT": 0.03,
    "BELIEF": 0.04,
    "SKILL": 0.02,
    "INSIGHT": 0.05,
    "GOAL": 0.06,
    "HUNCH": 0.08,
}

# ── Expression Thresholds (min confidence to influence behavior) ──

EXPRESSION_THRESHOLDS: dict[str, float] = {
    "FACT": 0.5,
    "BELIEF": 0.7,
    "SKILL": 0.6,
    "INSIGHT": 0.7,
    "GOAL": 0.3,
    "HUNCH": 0.8,
}

# Min reinforcement count for expression (type → count)
EXPRESSION_MIN_REINFORCEMENTS: dict[str, int] = {
    "FACT": 0,
    "BELIEF": 3,
    "SKILL": 2,
    "INSIGHT": 0,
    "GOAL": 0,
    "HUNCH": 0,
}

# ── Enzyme Types ──

class EnzymeType(str, Enum):
    REINFORCE = "REINFORCE"
    MUTATE = "MUTATE"
    DECAY = "DECAY"
    MERGE = "MERGE"
    EXPRESS = "EXPRESS"
    SPLICE = "SPLICE"


# ── Dataclasses ──

@dataclass
class Gene:
    """Atomic unit of agent knowledge. Always has a plain English name + description."""
    id: int | None = None
    agent: str = ""
    user_id: str = ""
    gene_type: str = "FACT"
    name: str = ""              # Plain English name, e.g. "Prefers remote roles"
    description: str = ""       # Longer explanation of what this gene means
    content: str = ""           # Raw content/evidence backing this gene
    confidence: float = 0.5
    reinforcement_count: int = 0
    decay_rate: float = 0.03
    parent_gene_id: int | None = None
    source: str = ""            # Where this gene came from (bot run, user action, splice, etc.)
    tags: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    expressed: bool = False
    archived: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_reinforced_at: datetime | None = None

    @property
    def is_expressible(self) -> bool:
        """Check if this gene passes expression threshold."""
        threshold = EXPRESSION_THRESHOLDS.get(self.gene_type, 0.5)
        min_reinforcements = EXPRESSION_MIN_REINFORCEMENTS.get(self.gene_type, 0)
        return (
            self.confidence >= threshold
            and self.reinforcement_count >= min_reinforcements
            and not self.archived
        )

    def to_yaml_dict(self) -> dict:
        """Serialize to a human-readable YAML-friendly dict."""
        d: dict = {
            "name": self.name,
            "type": self.gene_type,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "reinforcements": self.reinforcement_count,
            "source": self.source,
        }
        if self.tags:
            d["tags"] = self.tags
        if self.expressed:
            d["expressed"] = True
        if self.archived:
            d["archived"] = True
        return d


@dataclass
class Mutation:
    """Audit log entry for gene modifications."""
    id: int | None = None
    gene_id: int = 0
    agent: str = ""
    user_id: str = ""
    enzyme: str = ""
    old_confidence: float = 0.0
    new_confidence: float = 0.0
    reason: str = ""
    created_at: datetime | None = None


@dataclass
class PulseConfig:
    """Per-agent pulse schedule and behavior config."""
    agent: str = ""
    user_id: str = ""
    enabled: bool = True
    frequency_minutes: int = 60
    active_hours_start: int = 6    # UTC hour
    active_hours_end: int = 22     # UTC hour
    cooldown_minutes: int = 5
    max_actions_per_pulse: int = 3
    expression_bias: float = 0.5   # 0 = conservative, 1 = eager to express


@dataclass
class PulseLog:
    """Record of what happened during a pulse cycle."""
    id: int | None = None
    agent: str = ""
    user_id: str = ""
    genes_decayed: int = 0
    genes_reinforced: int = 0
    genes_expressed: int = 0
    genes_merged: int = 0
    genes_spliced: int = 0
    actions_taken: list[str] = field(default_factory=list)
    duration_ms: int = 0
    created_at: datetime | None = None
