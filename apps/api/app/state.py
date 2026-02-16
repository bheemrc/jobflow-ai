from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


def _add_or_reset_list(existing: list, new: list) -> list:
    """Concatenate lists, but RESET to empty when new is an empty list.

    This lets parallel agents append via [item], while the coach can
    clear the accumulator at the start of a turn by returning [].
    """
    if not new:
        return []
    return existing + new


@dataclass
class AgentState:
    """Shared state for the orchestrator graph.

    Fields written by parallel agents use Annotated reducers so that
    concurrent updates merge cleanly instead of overwriting each other.
    """

    # Conversation messages (auto-appended via add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)

    # User context
    resume_id: str = ""
    resume_text: str = ""
    resume_profile: dict = field(default_factory=dict)
    target_company: str = ""
    target_role: str = ""
    job_status: str = ""  # saved, applied, interview, offer, rejected
    job_description: str = ""

    # Focus room topic — constrains coach routing to a specific topic
    focus_topic: str = ""

    # Agent routing — coach sets this list, Send() reads it
    dispatched_agents: list[str] = field(default_factory=list)

    # Keyed agent outputs — each parallel agent writes {agent_name: text}
    # operator.or_ merges dicts: {"a": 1} | {"b": 2} = {"a": 1, "b": 2}
    agent_outputs: Annotated[dict[str, str], operator.or_] = field(default_factory=dict)

    # Approval workflow — keyed by agent name for parallel approvals
    pending_approvals: Annotated[dict[str, dict], operator.or_] = field(default_factory=dict)
    approval_decisions: Annotated[dict[str, str], operator.or_] = field(default_factory=dict)

    # Active agents tracking — merged across parallel agents
    active_agents: Annotated[dict[str, str], operator.or_] = field(default_factory=dict)

    # Sections generated — concatenated across parallel agents, reset on empty
    sections_generated: Annotated[list[str], _add_or_reset_list] = field(default_factory=list)

    # Structured section cards — concatenated across parallel agents, reset on empty
    section_cards: Annotated[list[dict], _add_or_reset_list] = field(default_factory=list)
