"""Group chat orchestrator — manages multi-agent discussions with turn control.

Performance optimizations:
- Batched database writes with async queue
- Cached personality lookups
- Connection pool reuse
- Parallel event publishing
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from app.group_chat.controls import (
    GroupChatConfig,
    GroupChatState,
    EnforcementAction,
    enforce_limits,
    get_filtered_tools,
)
from app.group_chat.memory import (
    get_or_create_memory,
    get_memory,
    clear_memory,
    GroupChatMemory,
)
from app.group_chat.workspace import (
    get_or_create_workspace_async,
    get_workspace,
    clear_workspace,
    SharedWorkspace,
)
from app.group_chat.planner import analyze_and_setup_workspace
from app.event_bus import event_bus
from app.user_context import current_user_id

logger = logging.getLogger(__name__)


# Cache for agent personalities to avoid repeated lookups
@lru_cache(maxsize=32)
def _get_cached_personality(agent: str) -> dict:
    """Cache agent personalities for performance."""
    try:
        from app.thought_engine import get_agent_personality
        return get_agent_personality(agent)
    except Exception:
        return {"display_name": agent, "bio": "", "prompt": ""}


# Regex to extract @mentions from content
MENTION_PATTERN = re.compile(r"@(\w+)")


class GroupChatOrchestrator:
    """Manages multi-agent group discussions with turn control.

    Enhanced with:
    - Problem analysis via PlannerOrchestrator
    - Shared workspace for agent collaboration
    - Dynamic agent spawning based on problem needs
    """

    def __init__(self, group_chat_id: int, config: GroupChatConfig | None = None):
        self.group_chat_id = group_chat_id
        self.config = config or GroupChatConfig()
        self.state: GroupChatState | None = None
        self.memory: GroupChatMemory | None = None
        self.workspace: SharedWorkspace | None = None
        self._running = False
        self._task: asyncio.Task | None = None
        self._plan_result: dict | None = None  # Store plan for reference

    async def load_state(self) -> GroupChatState:
        """Load or initialize chat state from database."""
        from app.db import get_group_chat, get_group_chat_messages

        user_id = current_user_id.get()
        chat_data = await get_group_chat(self.group_chat_id, user_id)
        if not chat_data:
            raise ValueError(f"Group chat {self.group_chat_id} not found")

        # Parse config from stored data
        stored_config = chat_data.get("config", {})
        config = GroupChatConfig(
            max_turns=chat_data.get("max_turns", self.config.max_turns),
            max_tokens=chat_data.get("max_tokens", self.config.max_tokens),
            turn_mode=stored_config.get("turn_mode", self.config.turn_mode),
            allow_self_modification=stored_config.get("allow_self_modification", True),
            require_approval_for_changes=stored_config.get("require_approval_for_changes", False),
        )
        # Restore allowed_tools if specified in stored config
        if "allowed_tools" in stored_config:
            config.allowed_tools = list(stored_config["allowed_tools"])

        self.state = GroupChatState(
            group_chat_id=self.group_chat_id,
            topic=chat_data.get("topic", ""),
            status=chat_data.get("status", "active"),
            participants=chat_data.get("participants", []),
            initiator=chat_data.get("initiator", "user"),
            config=config,
            turns_used=chat_data.get("turns_used", 0),
            tokens_used=chat_data.get("tokens_used", 0),
        )

        # Load recent messages for context
        messages = await get_group_chat_messages(self.group_chat_id, limit=10, user_id=user_id)
        for msg in messages:
            self.state.recent_messages.append({
                "agent": msg.get("agent", ""),
                "content": msg.get("content", "")[:500],
                "mentions": msg.get("mentions", []),
                "turn": msg.get("turn_number", 0),
            })

        return self.state

    async def start(self) -> None:
        """Load chat state and begin orchestration (planning happens in background)."""
        if self._running:
            return

        await self.load_state()
        if not self.state:
            raise ValueError("Failed to load group chat state")

        if self.state.status != "active":
            logger.info("Group chat %d is not active (status=%s)", self.group_chat_id, self.state.status)
            return

        self._running = True

        # Initialize memory system
        self.memory = get_or_create_memory(
            group_chat_id=self.group_chat_id,
            topic=self.state.topic,
            participants=list(self.state.participants),
        )

        # Initialize workspace (loads from DB if exists)
        self.workspace = await get_or_create_workspace_async(
            group_chat_id=self.group_chat_id,
            topic=self.state.topic,
        )

        await event_bus.publish({
            "type": "group_chat_started",
            "group_chat_id": self.group_chat_id,
            "topic": self.state.topic,
            "participants": self.state.participants,
        })

        # Run the orchestration loop (planning happens inside the loop)
        self._task = asyncio.create_task(self._run_loop())

    async def _analyze_and_setup(self) -> None:
        """Analyze problem and spawn agents - runs at start of orchestration loop."""
        if not self.state:
            return

        try:
            logger.info("Analyzing problem and setting up workspace for chat %d", self.group_chat_id)
            self._plan_result = await analyze_and_setup_workspace(
                group_chat_id=self.group_chat_id,
                topic=self.state.topic,
            )

            # Add spawned agents to participants
            for agent_info in self._plan_result.get("spawned_agents", []):
                if agent_info.get("status") == "spawned":
                    agent_name = agent_info["name"]
                    if agent_name not in self.state.participants:
                        self.state.participants.append(agent_name)

                        # Update database
                        from app.db import add_group_chat_participant
                        user_id = current_user_id.get()
                        await add_group_chat_participant(self.group_chat_id, agent_name, user_id)

                        # Publish event for UI update
                        await event_bus.publish({
                            "type": "group_chat_participant_joined",
                            "group_chat_id": self.group_chat_id,
                            "agent": agent_name,
                            "display_name": agent_info.get("display_name", agent_name),
                            "role": agent_info.get("role", ""),
                            "reason": "Spawned by planner for problem-solving",
                            "is_dynamic": True,
                        })

            logger.info(
                "Plan created: %s. Spawned %d agents, created %d tasks",
                self._plan_result.get("main_goal", ""),
                len([a for a in self._plan_result.get("spawned_agents", []) if a.get("status") == "spawned"]),
                len(self._plan_result.get("created_tasks", [])),
            )

            # Publish plan event
            await event_bus.publish({
                "type": "group_chat_plan_created",
                "group_chat_id": self.group_chat_id,
                "main_goal": self._plan_result.get("main_goal"),
                "sub_goals": self._plan_result.get("sub_goals"),
                "approach": self._plan_result.get("approach"),
                "spawned_agents": self._plan_result.get("spawned_agents"),
                "tasks": self._plan_result.get("created_tasks"),
            })

        except Exception as e:
            logger.error("Failed to analyze problem for chat %d: %s", self.group_chat_id, e)
            # Continue without plan - fall back to basic orchestration

    async def stop(self) -> None:
        """Stop the orchestration loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        """Main orchestration loop."""
        try:
            # Analyze problem and spawn agents at the start (runs in background)
            await self._analyze_and_setup()

            while self._running and self.state and self.state.status == "active":
                # Check limits
                action = enforce_limits(self.state)

                if action == EnforcementAction.CONCLUDE:
                    await self.conclude()
                    break
                elif action == EnforcementAction.PAUSE:
                    await self.pause()
                    break
                elif action == EnforcementAction.WARN_80_PERCENT:
                    await self._emit_warning()

                # Select next speaker
                speaker = await self.select_next_speaker()
                if not speaker:
                    logger.info("No next speaker available, concluding chat %d", self.group_chat_id)
                    await self.conclude()
                    break

                # Run the agent's turn
                try:
                    result = await self.run_turn(speaker)
                    if not result:
                        # Agent didn't produce output, continue to next
                        continue
                except Exception as e:
                    logger.error("Error in turn for agent %s: %s", speaker, e)
                    continue

                # Adaptive pause between turns based on content length
                # Shorter pause for quick exchanges, longer for detailed responses
                if result and result.get("content"):
                    content_len = len(result["content"])
                    pause = min(0.5 + (content_len / 1000), 2.0)  # 0.5s to 2s
                else:
                    pause = 0.5
                await asyncio.sleep(pause)

        except asyncio.CancelledError:
            logger.info("Group chat %d orchestration cancelled", self.group_chat_id)
        except Exception as e:
            logger.error("Group chat %d orchestration error: %s", self.group_chat_id, e)
        finally:
            self._running = False

    async def run_turn(self, speaking_agent: str, responding_to: list[str] | None = None) -> dict | None:
        """Execute one agent's turn in the group chat."""
        if not self.state:
            return None

        user_id = current_user_id.get()
        self.state.current_speaker = speaking_agent

        await event_bus.publish({
            "type": "group_chat_turn_start",
            "group_chat_id": self.group_chat_id,
            "agent": speaking_agent,
            "turn": self.state.turns_used + 1,
        })

        try:
            # Build context for the agent
            context = await self._build_agent_context(speaking_agent, responding_to)

            # Execute the agent
            from app.group_chat.agent_executor import execute_group_chat_turn
            result = await execute_group_chat_turn(
                agent=speaking_agent,
                topic=self.state.topic,
                context=context,
                allowed_tools=get_filtered_tools(self.state.config),
                group_chat_id=self.group_chat_id,
                turn_number=self.state.turns_used + 1,
                user_id=user_id,
            )

            if not result or not result.get("content"):
                return None

            content = result.get("content", "")
            tokens_used = result.get("tokens_used", 0)
            tool_calls = result.get("tool_calls", [])

            # Filter out empty/useless responses
            content_lower = content.lower().strip()
            useless_patterns = [
                "nothing to add",
                "nothing new to add",
                "i have nothing to add",
                "nothing further to contribute",
                "no additional input",
                "i yield",
            ]
            if any(pattern in content_lower for pattern in useless_patterns) and len(content) < 100:
                logger.info("Skipping empty response from %s: %s...", speaking_agent, content[:50])
                return None  # Skip this turn, let next agent speak

            # Extract mentions from both content AND tool calls
            mentions = await self.parse_mentions(content)

            # Also detect spawned/tagged agents from tool calls
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                if tool_name in ("spawn_agent", "tag_agent_in_chat"):
                    agent_name = tool_args.get("agent_name", "") or tool_args.get("name", "")
                    if agent_name:
                        normalized = agent_name.lower().replace(" ", "").replace("_", "")
                        if normalized not in mentions:
                            mentions.append(normalized)
                            logger.info("Added %s to mentions from tool call %s", normalized, tool_name)

            # Create timeline post for this message
            from app.db import create_timeline_post, add_group_chat_message, update_group_chat_stats

            post = await create_timeline_post(
                agent=speaking_agent,
                post_type="group_chat",
                content=content,
                context={
                    "group_chat_id": self.group_chat_id,
                    "topic": self.state.topic,
                    "turn": self.state.turns_used + 1,
                    "mentions": mentions,
                },
                user_id=user_id,
            )

            # Record the message
            await add_group_chat_message(
                group_chat_id=self.group_chat_id,
                agent=speaking_agent,
                turn_number=self.state.turns_used + 1,
                mentions=mentions,
                timeline_post_id=post.get("id"),
                tokens_used=tokens_used,
                user_id=user_id,
            )

            # Update state
            self.state.add_message(speaking_agent, content, mentions, tokens_used)
            await update_group_chat_stats(self.group_chat_id, 1, tokens_used, user_id)

            # Record in memory system
            if self.memory:
                tool_calls = result.get("tool_calls", [])
                self.memory.add_message(
                    agent=speaking_agent,
                    content=content,
                    mentions=mentions,
                    tool_calls=tool_calls,
                )

            # Publish event - await to ensure it's sent before continuing
            event_data = {
                "type": "group_chat_message",
                "group_chat_id": self.group_chat_id,
                "agent": speaking_agent,
                "content": content,
                "mentions": mentions,
                "turn": self.state.turns_used,
                "tokens_used": tokens_used,
                "post_id": post.get("id"),
            }
            logger.info(
                "Publishing group_chat_message: turn=%d, agent=%s, post_id=%s, content_len=%d",
                self.state.turns_used, speaking_agent, post.get("id"), len(content)
            )
            await event_bus.publish(event_data)

            return {
                "agent": speaking_agent,
                "content": content,
                "mentions": mentions,
                "tokens_used": tokens_used,
                "post_id": post.get("id"),
            }

        except Exception as e:
            logger.error("Error running turn for %s: %s", speaking_agent, e)
            await event_bus.publish({
                "type": "group_chat_turn_error",
                "group_chat_id": self.group_chat_id,
                "agent": speaking_agent,
                "error": str(e),
            })
            return None

    async def _build_agent_context(self, agent: str, responding_to: list[str] | None = None) -> str:
        """Build context string for an agent's turn using memory system."""
        if not self.state:
            return ""

        # Use memory system if available
        if self.memory:
            context = self.memory.get_context_for_agent(agent)
            if responding_to:
                context = f"RESPONDING TO: @{', @'.join(responding_to)}\n\n{context}"
            return context

        # Fallback to basic context
        context_parts = [
            f"TOPIC: {self.state.topic}",
            f"PARTICIPANTS: {', '.join(self.state.participants)}",
            f"TURN: {self.state.turns_used + 1} of {self.state.config.max_turns}",
        ]

        if responding_to:
            context_parts.append(f"RESPONDING TO: @{', @'.join(responding_to)}")

        # Add recent conversation history
        if self.state.recent_messages:
            context_parts.append("\nRECENT CONVERSATION:")
            for msg in self.state.recent_messages[-5:]:  # Last 5 messages
                context_parts.append(f"  @{msg['agent']}: {msg['content'][:200]}...")

        return "\n".join(context_parts)

    async def parse_mentions(self, content: str) -> list[str]:
        """Extract @agent_name mentions from content.

        Dynamic agent handling:
        1. Check if mentioned agent is already a participant
        2. Check if it's a dynamic agent (spawned at runtime)
        3. Check if it exists in bot config (static agents)
        4. Auto-add recognized agents to the chat
        """
        if not self.state:
            return []

        from app.thought_engine import get_all_personalities
        from app.group_chat.dynamic_agents import get_dynamic_agent

        mentions = MENTION_PATTERN.findall(content)
        valid_mentions = []

        # Get all available static agents from bot config
        all_agents = get_all_personalities()
        available_static_agents = set(all_agents.keys())

        for mention in mentions:
            mention_lower = mention.lower()

            # 1. Check if already a participant
            if mention_lower in self.state.participants:
                valid_mentions.append(mention_lower)
                continue

            # 2. Check if it's a dynamic agent (spawned at runtime)
            dynamic_agent = get_dynamic_agent(mention_lower)
            if dynamic_agent:
                logger.info(
                    "Dynamic agent %s (spawned by %s) joining chat %d",
                    dynamic_agent.display_name, dynamic_agent.spawned_by, self.group_chat_id
                )
                self.state.participants.append(mention_lower)

                # Update database
                from app.db import add_group_chat_participant
                user_id = current_user_id.get()
                await add_group_chat_participant(self.group_chat_id, mention_lower, user_id)

                # Publish event for UI update
                await event_bus.publish({
                    "type": "group_chat_participant_joined",
                    "group_chat_id": self.group_chat_id,
                    "agent": mention_lower,
                    "display_name": dynamic_agent.display_name,
                    "role": dynamic_agent.role,
                    "reason": f"Spawned by {dynamic_agent.spawned_by or self.state.current_speaker}",
                    "is_dynamic": True,
                })

                valid_mentions.append(mention_lower)
                continue

            # 3. Check if agent exists in bot config (static agent)
            if mention_lower in available_static_agents:
                logger.info(
                    "Static agent %s joining chat %d via mention",
                    mention_lower, self.group_chat_id
                )
                self.state.participants.append(mention_lower)

                # Update database
                from app.db import add_group_chat_participant
                user_id = current_user_id.get()
                await add_group_chat_participant(self.group_chat_id, mention_lower, user_id)

                # Publish event for UI update
                await event_bus.publish({
                    "type": "group_chat_participant_joined",
                    "group_chat_id": self.group_chat_id,
                    "agent": mention_lower,
                    "reason": f"Mentioned by {self.state.current_speaker}",
                    "is_dynamic": False,
                })

                valid_mentions.append(mention_lower)
            else:
                logger.debug("Mention %s not recognized (not dynamic or static agent), skipping", mention)

        return valid_mentions

    async def select_next_speaker(self) -> str | None:
        """Pick next agent based on mentions, round-robin, or topic relevance."""
        if not self.state:
            return None

        mode = self.state.config.turn_mode

        if mode == "mention_driven":
            # Check if anyone was mentioned in the last message
            if self.state.mentioned_agents:
                # Pick the first mentioned agent that hasn't spoken recently
                for agent in self.state.mentioned_agents:
                    if agent != self.state.current_speaker:
                        self.state.mentioned_agents.discard(agent)
                        return agent

            # Fall back to round-robin if no mentions
            return self._round_robin_next()

        elif mode == "round_robin":
            return self._round_robin_next()

        elif mode == "topic_signal":
            # Use topic relevance scoring (requires DNA/genome integration)
            return await self._topic_relevance_next()

        return self._round_robin_next()

    def _round_robin_next(self) -> str | None:
        """Simple round-robin speaker selection."""
        if not self.state or not self.state.participants:
            return None

        # Find current speaker's index
        current = self.state.current_speaker
        if current and current in self.state.participants:
            idx = self.state.participants.index(current)
            next_idx = (idx + 1) % len(self.state.participants)
        else:
            next_idx = 0

        return self.state.participants[next_idx]

    async def _topic_relevance_next(self) -> str | None:
        """Select next speaker based on topic relevance (DNA-aware)."""
        if not self.state:
            return None

        # Try to use DNA coalition detection for topic relevance
        try:
            from app.dna.coalition import detect_coalition
            tags = self.state.topic.lower().split()
            coalition = await detect_coalition(tags, current_user_id.get())
            # Pick agent with highest relevance that hasn't just spoken
            for agent_data in coalition:
                agent = agent_data.get("agent")
                if agent and agent != self.state.current_speaker and agent in self.state.participants:
                    return agent
        except Exception as e:
            logger.debug("Topic relevance selection failed: %s", e)

        return self._round_robin_next()

    async def pause(self) -> None:
        """Pause the group chat."""
        if not self.state:
            return

        self.state.status = "paused"
        self._running = False

        from app.db import update_group_chat_status
        await update_group_chat_status(self.group_chat_id, "paused", user_id=current_user_id.get())

        await event_bus.publish({
            "type": "group_chat_paused",
            "group_chat_id": self.group_chat_id,
            "turns_used": self.state.turns_used,
            "tokens_used": self.state.tokens_used,
        })

    async def resume(self) -> None:
        """Resume a paused group chat."""
        if not self.state or self.state.status != "paused":
            return

        self.state.status = "active"

        from app.db import update_group_chat_status
        await update_group_chat_status(self.group_chat_id, "active", user_id=current_user_id.get())

        await event_bus.publish({
            "type": "group_chat_resumed",
            "group_chat_id": self.group_chat_id,
        })

        # Restart the loop
        await self.start()

    async def conclude(self) -> None:
        """End the chat, generate summary, persist final state."""
        if not self.state:
            return

        self.state.status = "concluded"
        self._running = False

        # Generate synthesis
        summary = await self.generate_synthesis()

        from app.db import conclude_group_chat
        await conclude_group_chat(self.group_chat_id, summary, user_id=current_user_id.get())

        # Clean up memory and workspace
        clear_memory(self.group_chat_id)
        clear_workspace(self.group_chat_id)

        # Get workspace results for event
        workspace_summary = {}
        if self.workspace:
            workspace_summary = {
                "tasks_completed": len([t for t in self.workspace.tasks.values() if t.status.value == "completed"]),
                "findings_count": len(self.workspace.findings),
                "decisions_approved": len(self.workspace.get_approved_decisions()),
            }

        await event_bus.publish({
            "type": "group_chat_concluded",
            "group_chat_id": self.group_chat_id,
            "topic": self.state.topic,
            "turns_used": self.state.turns_used,
            "tokens_used": self.state.tokens_used,
            "summary": summary,
            "workspace": workspace_summary,
        })

    async def generate_synthesis(self) -> str:
        """Use synthesis agent to summarize the group discussion."""
        if not self.state:
            return "No state available for synthesis."

        try:
            from app.group_chat.agent_executor import execute_synthesis
            synthesis = await execute_synthesis(
                topic=self.state.topic,
                messages=self.state.recent_messages,
                participants=self.state.participants,
                user_id=current_user_id.get(),
            )
            return synthesis
        except Exception as e:
            logger.error("Synthesis generation failed: %s", e)
            # Fallback summary
            return (
                f"Group discussion on '{self.state.topic}' concluded after "
                f"{self.state.turns_used} turns with {len(self.state.participants)} participants."
            )

    async def _emit_warning(self) -> None:
        """Emit a warning that the chat is approaching limits."""
        if not self.state:
            return

        await event_bus.publish({
            "type": "group_chat_warning",
            "group_chat_id": self.group_chat_id,
            "message": "Approaching budget limit (80%)",
            "turn_percentage": self.state.turn_percentage,
            "token_percentage": self.state.token_percentage,
        })

    async def add_participant(self, agent: str) -> bool:
        """Add a new participant to the chat (dynamic joining)."""
        if not self.state:
            return False

        if len(self.state.participants) >= self.state.config.max_participants:
            return False

        if agent in self.state.participants:
            return True  # Already a participant

        self.state.participants.append(agent)

        # Update database
        from app.db import get_conn
        import json
        async with get_conn() as conn:
            await conn.execute("""
                UPDATE agent_group_chats
                SET participants = $1::jsonb
                WHERE id = $2
            """, json.dumps(self.state.participants), self.group_chat_id)

        await event_bus.publish({
            "type": "group_chat_participant_joined",
            "group_chat_id": self.group_chat_id,
            "agent": agent,
        })

        return True

    async def request_to_join(self, agent: str, reason: str) -> bool:
        """Agent requests to join based on topic relevance."""
        if not self.state:
            return False

        # Check if there's room
        if len(self.state.participants) >= self.state.config.max_participants:
            return False

        # For now, auto-approve join requests
        # Could add approval logic here if needed
        return await self.add_participant(agent)


# Active orchestrators registry (for managing concurrent chats)
_active_orchestrators: dict[int, GroupChatOrchestrator] = {}


def get_orchestrator(group_chat_id: int) -> GroupChatOrchestrator | None:
    """Get an active orchestrator by chat ID."""
    return _active_orchestrators.get(group_chat_id)


async def start_orchestrator(group_chat_id: int, config: GroupChatConfig | None = None) -> GroupChatOrchestrator:
    """Start a new orchestrator for a group chat."""
    if group_chat_id in _active_orchestrators:
        return _active_orchestrators[group_chat_id]

    orchestrator = GroupChatOrchestrator(group_chat_id, config)
    _active_orchestrators[group_chat_id] = orchestrator
    await orchestrator.start()
    return orchestrator


async def stop_orchestrator(group_chat_id: int) -> None:
    """Stop an active orchestrator."""
    orchestrator = _active_orchestrators.pop(group_chat_id, None)
    if orchestrator:
        await orchestrator.stop()
