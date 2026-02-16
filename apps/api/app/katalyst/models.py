"""Katalyst dataclasses — Reaction, Workstream, Artifact, Blocker, ReactionEvent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ReactionStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class WorkstreamStatus(str, Enum):
    PENDING = "pending"
    RESEARCH = "research"
    DRAFTING = "drafting"
    REFINING = "refining"
    REVIEW = "review"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ArtifactStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    FINAL = "final"
    SUPERSEDED = "superseded"


class BlockerSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Reaction:
    """Self-contained project spawned from a user goal."""
    id: int | None = None
    user_id: str = ""
    goal: str = ""
    status: str = "planning"
    lead_agent: str = ""
    phases: list[dict] = field(default_factory=list)  # [{name, status, order}]
    context: dict = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class Workstream:
    """Unit of work within a reaction, owned by one agent."""
    id: int | None = None
    reaction_id: int = 0
    user_id: str = ""
    title: str = ""
    description: str = ""
    agent: str = ""
    status: str = "pending"
    phase: str = ""
    order: int = 0
    progress: int = 0  # 0-100
    output: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Artifact:
    """Deliverable produced by a workstream — document, code, spec, etc."""
    id: int | None = None
    reaction_id: int = 0
    workstream_id: int | None = None
    user_id: str = ""
    title: str = ""
    artifact_type: str = "document"  # document, code, spec, analysis, report
    content: str = ""
    version: int = 1
    status: str = "draft"
    agent: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Blocker:
    """Problem requiring a decision — auto-resolved or escalated to user."""
    id: int | None = None
    reaction_id: int = 0
    workstream_id: int | None = None
    user_id: str = ""
    title: str = ""
    description: str = ""
    severity: str = "medium"
    agent: str = ""
    options: list[dict] = field(default_factory=list)  # [{label, description, confidence}]
    auto_resolve_confidence: float = 0.0  # If > 0.7, can auto-resolve
    resolution: str = ""
    resolved_by: str = ""  # "agent" or "user"
    created_at: datetime | None = None
    resolved_at: datetime | None = None


@dataclass
class ReactionEvent:
    """Activity feed entry for a reaction."""
    id: int | None = None
    reaction_id: int = 0
    user_id: str = ""
    event_type: str = ""  # phase_change, workstream_update, artifact_created, blocker_raised, etc.
    agent: str = ""
    message: str = ""
    data: dict = field(default_factory=dict)
    created_at: datetime | None = None
