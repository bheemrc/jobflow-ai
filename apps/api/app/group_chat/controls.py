"""Group chat configuration and state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EnforcementAction(Enum):
    """Actions returned by limit enforcement checks."""
    CONTINUE = "continue"
    WARN_80_PERCENT = "warn_80_percent"
    PAUSE = "pause"
    CONCLUDE = "conclude"


@dataclass
class GroupChatConfig:
    """Configuration for a group chat session."""
    max_turns: int = 15  # Reduced - fewer but more substantive turns
    max_tokens: int = 60000  # Token budget
    max_duration_seconds: int = 600  # 10 minutes - force density
    turn_timeout_seconds: int = 30
    turn_mode: str = "mention_driven"  # mention_driven, round_robin, topic_signal
    allow_self_modification: bool = True
    require_approval_for_changes: bool = False  # Fully autonomous per plan
    synthesis_agent: str = "nexus_synthesis"
    min_participants: int = 2
    max_participants: int = 6

    # Tool whitelist for group chats (research-only, no side effects)
    allowed_tools: list[str] = field(default_factory=lambda: [
        "web_search",
        "tag_agent_in_chat",
        "spawn_agent",  # Allow spawning dynamic specialists
        "propose_prompt_change",
        "review_resume",
        "extract_resume_profile",
        "get_search_history",
        "get_user_job_interests",
        "get_saved_jobs",
        "get_job_pipeline",
    ])

    # Tools blocked during group chats (have side effects)
    blocked_tools: list[str] = field(default_factory=lambda: [
        "save_job",
        "update_job_stage",
        "add_job_note",
        "send_notification",
        "call_webhook",
        "manage_bot",
    ])


@dataclass
class GroupChatState:
    """Runtime state for an active group chat."""
    group_chat_id: int
    topic: str
    status: str  # active, paused, concluded
    participants: list[str]
    initiator: str
    config: GroupChatConfig

    # Counters
    turns_used: int = 0
    tokens_used: int = 0

    # Turn management
    current_speaker: str | None = None
    next_speakers: list[str] = field(default_factory=list)
    mentioned_agents: set[str] = field(default_factory=set)

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_turn_at: datetime | None = None

    # History for context
    recent_messages: list[dict] = field(default_factory=list)

    @property
    def turn_percentage(self) -> float:
        """Percentage of turns used."""
        return (self.turns_used / self.config.max_turns * 100) if self.config.max_turns > 0 else 0

    @property
    def token_percentage(self) -> float:
        """Percentage of tokens used."""
        return (self.tokens_used / self.config.max_tokens * 100) if self.config.max_tokens > 0 else 0

    @property
    def duration_seconds(self) -> float:
        """Time elapsed since chat started."""
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def add_message(self, agent: str, content: str, mentions: list[str], tokens: int = 0) -> None:
        """Record a message in the state."""
        self.recent_messages.append({
            "agent": agent,
            "content": content[:500],  # Truncate for memory
            "mentions": mentions,
            "turn": self.turns_used,
        })
        # Keep only last 10 messages in memory
        if len(self.recent_messages) > 10:
            self.recent_messages = self.recent_messages[-10:]

        # Track mentions for next speaker selection
        for mention in mentions:
            if mention in self.participants:
                self.mentioned_agents.add(mention)

        self.turns_used += 1
        self.tokens_used += tokens
        self.last_turn_at = datetime.now(timezone.utc)


def enforce_limits(state: GroupChatState) -> EnforcementAction:
    """Check all limits and return required action."""
    config = state.config

    # Check hard limits
    if state.turns_used >= config.max_turns:
        return EnforcementAction.CONCLUDE

    if state.tokens_used >= config.max_tokens:
        return EnforcementAction.CONCLUDE

    if state.duration_seconds >= config.max_duration_seconds:
        return EnforcementAction.CONCLUDE

    # Check warning thresholds (80%)
    if state.turn_percentage >= 80 or state.token_percentage >= 80:
        return EnforcementAction.WARN_80_PERCENT

    # Check turn timeout
    if state.last_turn_at:
        since_last = (datetime.now(timezone.utc) - state.last_turn_at).total_seconds()
        if since_last >= config.turn_timeout_seconds * 2:  # Double timeout = pause
            return EnforcementAction.PAUSE

    return EnforcementAction.CONTINUE


def get_filtered_tools(config: GroupChatConfig) -> list[str]:
    """Get the list of tools allowed in this group chat."""
    return [t for t in config.allowed_tools if t not in config.blocked_tools]
