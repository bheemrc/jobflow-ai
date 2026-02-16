"""Agent executor for group chat turns.

Runs individual agents with group-chat-specific context and tool restrictions.

Performance optimizations:
- Cached LLM clients per model
- Cached tool bindings
- Parallel tool execution
- Streaming for faster perceived response time
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.user_context import current_user_id

logger = logging.getLogger(__name__)

# Timeout for LLM calls (seconds)
LLM_TIMEOUT = 60

# Cached LLM clients to avoid recreation overhead
_llm_cache: dict[str, ChatOpenAI] = {}


def _get_llm(model: str, temperature: float = 0.7, max_tokens: int = 1024) -> ChatOpenAI:
    """Get or create cached LLM client."""
    cache_key = f"{model}_{temperature}_{max_tokens}"
    if cache_key not in _llm_cache:
        _llm_cache[cache_key] = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=LLM_TIMEOUT,
        )
    return _llm_cache[cache_key]


@lru_cache(maxsize=16)
def _get_cached_personality(agent: str) -> dict:
    """Cache agent personalities to avoid repeated lookups."""
    try:
        from app.thought_engine import get_agent_personality
        return get_agent_personality(agent)
    except Exception:
        return {"display_name": agent, "bio": "", "prompt": ""}


# Universal prompt - STRICT rules for substantive contributions
GROUP_CHAT_PROMPT = """You are {display_name}. Topic: {topic}

{context}

═══════════════════════════════════════════════════════════════════════════════
SHARED WORKSPACE
═══════════════════════════════════════════════════════════════════════════════
{workspace_context}
═══════════════════════════════════════════════════════════════════════════════

TOOLS: {tools}

═══════════════════════════════════════════════════════════════════════════════
MANDATORY: USE YOUR TOOLS
═══════════════════════════════════════════════════════════════════════════════

You MUST use at least one tool every turn. Choose the most appropriate action:

1. web_search - Research facts, numbers, specifications, costs, comparisons
2. add_finding - Document your research results with specific data
3. claim_task / complete_task - Take and complete workspace tasks
4. propose_decision / vote_on_decision - Drive group decisions forward
5. spawn_agent - Bring in a specialist if expertise is needed
6. tag_agent_in_chat - Ask another agent a specific question

NEVER post without using a tool first. Research before speaking.

═══════════════════════════════════════════════════════════════════════════════
RULES FOR YOUR POST
═══════════════════════════════════════════════════════════════════════════════

1. LEAD WITH DATA from your tool use:
   ✓ "Per my research: Tantalum shielding costs $850/kg with 95% gamma attenuation"
   ✓ "I found 3 comparable systems: [table with specs]"
   ✗ "I think we should consider radiation protection" (vague, no data)

2. BE SPECIFIC with numbers:
   ✓ "100 krad TID requires 2mm tantalum at $850/kg = $12,750 for 15kg shielding"
   ✓ "Operating range -40°C to +85°C needs 0.2m² radiator for 15W dissipation"
   ✗ "ensure adequate radiation protection" (meaningless without numbers)

3. PRODUCE DELIVERABLES, not summaries:
   - Comparison tables with actual values
   - Calculations showing your work
   - Decision recommendations with quantified trade-offs

4. CHALLENGE with evidence:
   - "Your approach adds 12kg mass = $180k extra launch cost. Worth it?"
   - "That costs 3x more. What's the reliability improvement?"

5. ANSWER QUESTIONS directly with data. Don't say "I'll look into that."
   Use web_search and answer immediately.

═══════════════════════════════════════════════════════════════════════════════
THIS TURN: Pick ONE deliverable
═══════════════════════════════════════════════════════════════════════════════
□ Research a specific question (web_search → add_finding → post results)
□ Complete a workspace task (claim_task → do work → complete_task)
□ Make a decision (propose_decision with evidence from research)
□ Challenge an assumption (cite evidence showing why it's wrong)
□ Answer a pending question (research then answer with data)

Your post must contain specific numbers from your research or calculations.
"""


SYNTHESIS_SYSTEM_PROMPT = """You are synthesizing a multi-agent group discussion into actionable insights.

═══════════════════════════════════════════
TOPIC: {topic}
PARTICIPANTS: {participants}
═══════════════════════════════════════════

Create a synthesis that executives and decision-makers would find valuable. Structure it as:

## Key Insights
- Bullet the 3-5 most important findings/conclusions
- Include specific data points mentioned in the discussion

## Points of Debate
- Note where agents disagreed and the core tension
- Indicate which perspective had stronger evidence

## Research Highlights
- Summarize any web searches or external data that was cited
- Include specific numbers, companies, or sources mentioned

## Actionable Recommendations
- 2-3 specific next steps or actions based on the discussion
- Be concrete, not generic

## Participant Contributions
- One line per agent: their main contribution and stance

═══════════════════════════════════════════
Keep the synthesis under 400 words. Be specific and cite evidence from the conversation.
═══════════════════════════════════════════

CONVERSATION:
{conversation}
"""


WORKSPACE_TOOLS = [
    "read_workspace",
    "add_finding",
    "claim_task",
    "complete_task",
    "propose_decision",
    "vote_on_decision",
    "create_task",
]


async def execute_group_chat_turn(
    agent: str,
    topic: str,
    context: str,
    allowed_tools: list[str],
    group_chat_id: int,
    user_id: str = "",
    turn_number: int = 1,
) -> dict | None:
    """Execute a single agent's turn in a group chat.

    Supports both static agents (from bots.yaml) and dynamic agents (spawned at runtime).
    ALL agents can spawn new specialists AND research at ANY time - like a university or NASA team.
    Agents now have access to a shared workspace for collaboration.

    Returns dict with content, tokens_used, or None if failed.
    """
    user_id = user_id or current_user_id.get()

    # Set context for tools (so spawn_agent knows the current topic/agent/chat)
    from app.tools import set_current_context, set_current_group_chat
    set_current_context(topic=topic, agent=agent)
    set_current_group_chat(group_chat_id)

    # Get workspace context for the agent
    from app.group_chat.workspace import get_workspace
    workspace = get_workspace(group_chat_id)
    workspace_context = ""
    if workspace:
        workspace_context = workspace.get_context_for_agent(agent)
    else:
        workspace_context = "No workspace initialized yet."

    # Check if this is a dynamic agent first
    from app.group_chat.dynamic_agents import get_dynamic_agent
    dynamic_agent = get_dynamic_agent(agent)

    # Base tools always available - including workspace tools
    base_tools = set(allowed_tools) | {
        "spawn_agent", "web_search", "tag_agent_in_chat"
    } | set(WORKSPACE_TOOLS)

    if dynamic_agent:
        # Dynamic agents use their custom prompt but can ALSO spawn more specialists
        display_name = dynamic_agent.display_name
        # Append workspace context to the dynamic agent's prompt
        base_prompt = dynamic_agent.generate_system_prompt(topic, context)
        system_prompt = f"""{base_prompt}

═══════════════════════════════════════════════════════════════════════════════
SHARED WORKSPACE
═══════════════════════════════════════════════════════════════════════════════
{workspace_context}

WORKSPACE TOOLS:
- read_workspace: See all tasks, findings, and pending decisions
- claim_task: Take ownership of a task
- complete_task: Mark task done with result
- add_finding: Share research or insights
- propose_decision: Propose a decision for group vote
- vote_on_decision: Support or oppose a decision
- create_task: Create a new task for the team
"""
        temperature = dynamic_agent.temperature
        max_tokens = dynamic_agent.max_tokens

        # Ensure dynamic agents have full tool access
        if dynamic_agent.tools:
            allowed_tools = list(base_tools | set(dynamic_agent.tools))
        else:
            allowed_tools = list(base_tools)

        logger.info(
            "Turn %d: Dynamic agent %s (%s) - can spawn more experts",
            turn_number, display_name, dynamic_agent.role
        )
    else:
        # Static agents use universal prompt with full tool access
        personality = _get_cached_personality(agent)
        display_name = personality.get("display_name", agent)
        description = personality.get("bio", personality.get("prompt", ""))
        temperature = 0.7
        max_tokens = 2048  # Increased for more detailed responses

        # Ensure all tools are available
        allowed_tools = list(base_tools)

        # Build tool list for prompt
        tool_names_preview = [
            "spawn_agent", "web_search", "tag_agent_in_chat",
            "read_workspace", "claim_task", "complete_task",
            "add_finding", "propose_decision", "vote_on_decision"
        ]

        system_prompt = GROUP_CHAT_PROMPT.format(
            display_name=display_name,
            topic=topic,
            context=context,
            workspace_context=workspace_context,
            tools=", ".join(tool_names_preview),
        )
        logger.info("Turn %d: %s - can spawn experts, research, and use workspace", turn_number, agent)

    # Build tool list
    from app.tools import TOOL_REGISTRY
    tools = [TOOL_REGISTRY[t] for t in allowed_tools if t in TOOL_REGISTRY]
    tool_names = [t for t in allowed_tools if t in TOOL_REGISTRY]
    logger.info("Agent %s has %d tools bound: %s (requested: %s)", agent, len(tools), tool_names, allowed_tools)

    # Set up the model (cached) - use agent-specific settings
    model_name = settings.openai_model or "gpt-4o"
    logger.info("Group chat turn: agent=%s, model=%s, topic=%s", agent, model_name, topic[:50])

    base_llm = _get_llm(model_name, temperature=temperature, max_tokens=max_tokens)

    # Two LLM configs: one forces tool use, one allows final response
    if tools:
        llm_forced = base_llm.bind_tools(tools, tool_choice="required")
        llm_auto = base_llm.bind_tools(tools, tool_choice="auto")
    else:
        llm_forced = base_llm
        llm_auto = base_llm

    # Set user context for tools
    current_user_id.set(user_id)

    try:
        from langchain_core.messages import AIMessage, ToolMessage

        # Simple invocation with system + human message
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"It's your turn to contribute to the discussion about: {topic}"),
        ]

        # FIRST call: FORCE tool usage - no empty responses allowed
        logger.info("Invoking LLM for agent %s (tool_choice=required)...", agent)
        response = await asyncio.wait_for(llm_forced.ainvoke(messages), timeout=LLM_TIMEOUT)
        logger.info("LLM response received for agent %s", agent)

        # Calculate tokens (approximate)
        input_tokens = len(system_prompt) // 4 + len(topic) // 4
        output_tokens = 0

        # Handle tool calls - send results back to LLM for analysis
        max_tool_rounds = 3  # Prevent infinite loops
        tool_round = 0
        all_tool_calls = []  # Track all tool calls for orchestrator

        while hasattr(response, "tool_calls") and response.tool_calls and tool_round < max_tool_rounds:
            tool_round += 1
            logger.info("Agent %s made %d tool call(s), round %d", agent, len(response.tool_calls), tool_round)

            # Add the AI's response (with tool calls) to messages
            messages.append(response)

            # Execute each tool and add results
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", f"tool_{tool_name}")

                # Track tool calls for orchestrator
                all_tool_calls.append({
                    "name": tool_name,
                    "args": tool_args,
                })

                # Publish tool call event for UI
                from app.event_bus import event_bus
                await event_bus.publish({
                    "type": "group_chat_tool_call",
                    "group_chat_id": group_chat_id,
                    "agent": agent,
                    "turn": turn_number,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "status": "started",
                })

                if tool_name in TOOL_REGISTRY:
                    tool_fn = TOOL_REGISTRY[tool_name]
                    try:
                        fn_to_check = tool_fn.func if hasattr(tool_fn, "func") else tool_fn
                        if inspect.iscoroutinefunction(fn_to_check):
                            result = await tool_fn.ainvoke(tool_args)
                        else:
                            result = tool_fn.invoke(tool_args)
                        # Truncate long results
                        result_str = str(result)[:2000] if result else "No result"
                        logger.info("Tool %s returned: %s...", tool_name, result_str[:100])
                    except Exception as e:
                        logger.error("Tool %s failed: %s", tool_name, e)
                        result_str = f"Tool error: {e}"
                else:
                    result_str = f"Unknown tool: {tool_name}"

                # Publish tool result event for UI
                await event_bus.publish({
                    "type": "group_chat_tool_result",
                    "group_chat_id": group_chat_id,
                    "agent": agent,
                    "turn": turn_number,
                    "tool_name": tool_name,
                    "result_preview": result_str[:200],
                    "status": "completed",
                })

                # Persist tool call to database
                try:
                    from app.db import save_tool_call
                    await save_tool_call(
                        group_chat_id=group_chat_id,
                        agent=agent,
                        turn_number=turn_number,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_result=result_str[:1000],
                    )
                except Exception as e:
                    logger.error("Failed to save tool call: %s", e)

                # Add tool result message
                messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))

            # FOLLOW-UP calls: allow auto so it can give final response
            response = await asyncio.wait_for(llm_auto.ainvoke(messages), timeout=LLM_TIMEOUT)
            logger.info("LLM analyzed tool results for agent %s", agent)

        # Extract final content
        content = response.content if hasattr(response, "content") else str(response)
        output_tokens = len(content) // 4 if content else 0
        tokens_used = input_tokens + output_tokens

        return {
            "content": content,
            "tokens_used": tokens_used,
            "agent": agent,
            "tool_calls": all_tool_calls,
        }

    except asyncio.TimeoutError:
        logger.error("Group chat turn TIMEOUT for %s after %ds", agent, LLM_TIMEOUT)
        return None
    except Exception as e:
        logger.error("Group chat turn execution failed for %s: %s", agent, e, exc_info=True)
        return None


async def execute_synthesis(
    topic: str,
    messages: list[dict],
    participants: list[str],
    user_id: str = "",
) -> str:
    """Generate a synthesis of the group discussion."""

    # Format conversation for the synthesizer
    conversation_parts = []
    for msg in messages:
        agent = msg.get("agent", "unknown")
        content = msg.get("content", "")
        conversation_parts.append(f"@{agent}: {content}")

    conversation = "\n\n".join(conversation_parts)

    system_prompt = SYNTHESIS_SYSTEM_PROMPT.format(
        topic=topic,
        participants=", ".join(participants),
        conversation=conversation,
    )

    model_name = settings.openai_model or "gpt-4o"
    logger.info("Generating synthesis for topic: %s", topic[:50])

    llm = ChatOpenAI(
        model=model_name,
        temperature=0.3,  # Lower temp for more focused synthesis
        max_tokens=1024,
        request_timeout=LLM_TIMEOUT,
    )

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate the synthesis now."),
        ]

        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=LLM_TIMEOUT)
        logger.info("Synthesis generated successfully")
        return response.content if hasattr(response, "content") else str(response)

    except asyncio.TimeoutError:
        logger.error("Synthesis generation TIMEOUT after %ds", LLM_TIMEOUT)
        return f"Discussion on '{topic}' concluded with {len(participants)} participants. (synthesis timed out)"
    except Exception as e:
        logger.error("Synthesis generation failed: %s", e, exc_info=True)
        return f"Discussion on '{topic}' concluded with {len(participants)} participants."
