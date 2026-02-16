"""Agent memory system for group chats.

Maintains conversation context, agent perspectives, and shared knowledge
across turns for more coherent multi-agent discussions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Max messages to keep in context window
MAX_CONTEXT_MESSAGES = 20  # Increased for better conversation awareness
# Max tokens per agent's memory summary
MAX_MEMORY_TOKENS = 800


@dataclass
class AgentMemory:
    """Individual agent's memory within a group chat."""
    agent: str
    # Key points this agent has made
    contributions: list[str] = field(default_factory=list)
    # Points from other agents this agent has engaged with
    engagements: list[dict] = field(default_factory=list)
    # Agent's current stance/perspective on the topic
    perspective: str = ""
    # Tools this agent has used and their results
    tool_results: list[dict] = field(default_factory=list)
    # Agents this one has @mentioned or been mentioned by
    interaction_graph: dict[str, int] = field(default_factory=dict)

    def add_contribution(self, content: str, turn: int) -> None:
        """Record a contribution from this agent."""
        # Extract key points (first 200 chars or first sentence)
        key_point = content[:200].split(".")[0] + "."
        self.contributions.append(key_point)
        # Keep only recent contributions
        if len(self.contributions) > 10:
            self.contributions = self.contributions[-10:]

    def add_engagement(self, other_agent: str, engagement_type: str, turn: int) -> None:
        """Record an engagement with another agent."""
        self.engagements.append({
            "agent": other_agent,
            "type": engagement_type,
            "turn": turn,
        })
        # Track interaction frequency
        self.interaction_graph[other_agent] = self.interaction_graph.get(other_agent, 0) + 1

    def add_tool_result(self, tool: str, query: str, result_summary: str) -> None:
        """Record a tool usage."""
        self.tool_results.append({
            "tool": tool,
            "query": query[:100],
            "result": result_summary[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep only recent tool results
        if len(self.tool_results) > 5:
            self.tool_results = self.tool_results[-5:]

    def get_context_summary(self) -> str:
        """Generate a context summary for the agent's next turn."""
        parts = []

        if self.contributions:
            parts.append(f"Your key points so far: {'; '.join(self.contributions[-3:])}")

        if self.tool_results:
            recent = self.tool_results[-2:]
            tool_summary = "; ".join([f"{t['tool']}: {t['result'][:100]}" for t in recent])
            parts.append(f"Recent research: {tool_summary}")

        if self.interaction_graph:
            top_interactions = sorted(
                self.interaction_graph.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            agents = [a for a, _ in top_interactions]
            parts.append(f"You've been engaging most with: {', '.join(agents)}")

        return "\n".join(parts) if parts else ""


@dataclass
class SharedKnowledge:
    """Shared knowledge base for the group chat."""
    # Key facts established during discussion
    facts: list[dict] = field(default_factory=list)
    # Points of consensus
    consensus: list[str] = field(default_factory=list)
    # Points of disagreement
    disagreements: list[dict] = field(default_factory=list)
    # External data from tool calls
    research_findings: list[dict] = field(default_factory=list)

    def add_fact(self, fact: str, source_agent: str, confidence: float = 0.5) -> None:
        """Add a fact to shared knowledge."""
        self.facts.append({
            "fact": fact,
            "source": source_agent,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def add_research(self, query: str, findings: str, agent: str) -> None:
        """Add research findings from a tool call."""
        self.research_findings.append({
            "query": query,
            "findings": findings[:500],
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep only recent research
        if len(self.research_findings) > 10:
            self.research_findings = self.research_findings[-10:]

    def get_summary(self) -> str:
        """Get a summary of shared knowledge."""
        parts = []

        if self.research_findings:
            recent = self.research_findings[-3:]
            research = "; ".join([f"{r['query']}: {r['findings'][:100]}" for r in recent])
            parts.append(f"Research findings: {research}")

        if self.consensus:
            parts.append(f"Points of agreement: {'; '.join(self.consensus[-3:])}")

        if self.disagreements:
            recent = self.disagreements[-2:]
            debates = "; ".join([
                f"{d['topic']} ({d['agents'][0]} vs {d['agents'][1]})"
                for d in recent
            ])
            parts.append(f"Ongoing debates: {debates}")

        return "\n".join(parts) if parts else ""


class GroupChatMemory:
    """Memory manager for a group chat session."""

    def __init__(self, group_chat_id: int, topic: str, participants: list[str]):
        self.group_chat_id = group_chat_id
        self.topic = topic
        self.participants = participants

        # Individual agent memories
        self.agent_memories: dict[str, AgentMemory] = {
            agent: AgentMemory(agent=agent) for agent in participants
        }

        # Shared knowledge base
        self.shared = SharedKnowledge()

        # Recent message context (for LLM context window)
        self.recent_messages: list[dict] = []

        # Turn counter
        self.current_turn = 0

    def add_message(
        self,
        agent: str,
        content: str,
        mentions: list[str],
        tool_calls: list[dict] | None = None,
    ) -> None:
        """Process a new message and update memories."""
        self.current_turn += 1

        # Add to recent messages
        self.recent_messages.append({
            "agent": agent,
            "content": content[:1500],  # Keep more content for better context
            "mentions": mentions,
            "turn": self.current_turn,
        })

        # Keep context window limited
        if len(self.recent_messages) > MAX_CONTEXT_MESSAGES:
            self.recent_messages = self.recent_messages[-MAX_CONTEXT_MESSAGES:]

        # Update agent's memory
        if agent in self.agent_memories:
            mem = self.agent_memories[agent]
            mem.add_contribution(content, self.current_turn)

            # Record mentions as engagements
            for mentioned in mentions:
                if mentioned in self.agent_memories:
                    mem.add_engagement(mentioned, "mentioned", self.current_turn)
                    # Also record the reverse engagement
                    self.agent_memories[mentioned].add_engagement(
                        agent, "mentioned_by", self.current_turn
                    )

        # Process tool calls
        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.get("tool", "")
                query = tc.get("query", "")
                result = tc.get("result", "")

                if agent in self.agent_memories:
                    self.agent_memories[agent].add_tool_result(tool_name, query, result)

                if tool_name == "web_search" and result:
                    self.shared.add_research(query, result, agent)

    def get_context_for_agent(self, agent: str) -> str:
        """Build context string for an agent's next turn.

        Optimized for conversation quality:
        - Emphasizes recent messages that mention this agent
        - Shows what others have said that needs response
        - Provides awareness of conversation dynamics
        """
        parts = []

        # Topic and turn info
        parts.append(f"Turn {self.current_turn + 1} of the discussion")
        parts.append("")

        # Find messages that @mentioned this agent (needs response)
        needs_response = [
            msg for msg in self.recent_messages[-8:]
            if agent in msg.get("mentions", [])
        ]

        if needs_response:
            parts.append("🔔 YOU WERE TAGGED - RESPOND TO THIS:")
            for msg in needs_response[-2:]:  # Last 2 that mentioned this agent
                sender = msg["agent"]
                content = msg["content"][:400]
                parts.append(f"@{sender} said: \"{content}\"")
            parts.append("")

        # Full conversation history (ALL messages for complete context)
        if self.recent_messages:
            parts.append("📝 FULL DISCUSSION SO FAR:")
            for msg in self.recent_messages:
                sender = msg["agent"]
                content = msg["content"][:1200]  # Full content per message
                prefix = "→ " if sender == agent else "  "
                mentions_str = ""
                if msg["mentions"]:
                    mentions_str = f" (to @{', @'.join(msg['mentions'])})"
                parts.append(f"{prefix}@{sender}{mentions_str}: {content}")
            parts.append("")

            # Summarize each participant's key contribution
            parts.append("👥 PARTICIPANT CONTRIBUTIONS:")
            seen_agents = set()
            for msg in self.recent_messages:
                if msg["agent"] not in seen_agents:
                    seen_agents.add(msg["agent"])
                    # Get this agent's latest message as their "stance"
                    latest = [m for m in self.recent_messages if m["agent"] == msg["agent"]][-1]
                    parts.append(f"  • @{msg['agent']}: {latest['content'][:150]}...")
            parts.append("")

        # Who's been active vs quiet (for natural engagement)
        turn_counts = {}
        for msg in self.recent_messages:
            turn_counts[msg["agent"]] = turn_counts.get(msg["agent"], 0) + 1

        quiet_agents = [
            a for a in self.participants
            if a != agent and turn_counts.get(a, 0) < 2
        ]
        if quiet_agents and len(quiet_agents) <= 2:
            parts.append(f"💡 @{', @'.join(quiet_agents)} haven't spoken much — consider engaging them")
            parts.append("")

        # Agent's own memory
        if agent in self.agent_memories:
            agent_context = self.agent_memories[agent].get_context_summary()
            if agent_context:
                parts.append("📌 YOUR NOTES:")
                parts.append(agent_context)
                parts.append("")

        # Shared research findings (if any)
        if self.shared.research_findings:
            parts.append("🔍 RESEARCH CITED:")
            for r in self.shared.research_findings[-3:]:
                parts.append(f"  • {r['query']}: {r['findings'][:150]}...")
            parts.append("")

        return "\n".join(parts)

    def add_participant(self, agent: str) -> None:
        """Add a new participant mid-conversation."""
        if agent not in self.agent_memories:
            self.agent_memories[agent] = AgentMemory(agent=agent)
            self.participants.append(agent)

    def get_turn_summary(self) -> dict:
        """Get a summary of the current state for debugging/logging."""
        return {
            "group_chat_id": self.group_chat_id,
            "turn": self.current_turn,
            "participants": self.participants,
            "message_count": len(self.recent_messages),
            "research_count": len(self.shared.research_findings),
            "agent_interaction_counts": {
                agent: sum(mem.interaction_graph.values())
                for agent, mem in self.agent_memories.items()
            },
        }


# In-memory storage for active chat memories
_active_memories: dict[int, GroupChatMemory] = {}


def get_or_create_memory(
    group_chat_id: int,
    topic: str,
    participants: list[str],
) -> GroupChatMemory:
    """Get or create memory for a group chat."""
    if group_chat_id not in _active_memories:
        _active_memories[group_chat_id] = GroupChatMemory(
            group_chat_id=group_chat_id,
            topic=topic,
            participants=participants,
        )
    return _active_memories[group_chat_id]


def get_memory(group_chat_id: int) -> GroupChatMemory | None:
    """Get memory for a group chat if it exists."""
    return _active_memories.get(group_chat_id)


def clear_memory(group_chat_id: int) -> None:
    """Clear memory for a concluded group chat."""
    _active_memories.pop(group_chat_id, None)
