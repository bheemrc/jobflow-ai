"""Shared tool execution loop for agent nodes.

LangChain's model.bind_tools() tells the LLM about available tools,
but ainvoke() alone does NOT execute them. This module provides a loop
that actually calls the tool functions and feeds results back to the model.

Features:
- Parallel tool execution via asyncio.gather()
- Retry with exponential backoff for transient errors
- Optional output validation with self-correction

IMPORTANT: The RunnableConfig must be passed through so that LangGraph's
astream_events() can capture on_tool_start / on_tool_end events for the UI.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Sequence

import httpx
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6  # Safety limit to prevent infinite loops
MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0  # seconds


async def _execute_with_retry(
    tool_fn: BaseTool,
    tool_args: dict,
    config: RunnableConfig | None,
    *,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Execute a single tool with retry and exponential backoff."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = await tool_fn.ainvoke(tool_args, config=config)
            return str(result)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            last_error = e
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Tool %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    tool_fn.name, attempt + 1, max_retries + 1, delay, e,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("Tool %s failed after %d attempts: %s", tool_fn.name, max_retries + 1, e)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Tool %s error (attempt %d/%d), retrying in %.1fs: %s",
                    tool_fn.name, attempt + 1, max_retries + 1, delay, e,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("Tool %s failed after %d attempts: %s", tool_fn.name, max_retries + 1, e)

    return f"Error executing {tool_fn.name}: {last_error}"


async def _execute_tool(
    tool_map: dict[str, BaseTool],
    tool_call: dict,
    config: RunnableConfig | None,
) -> ToolMessage:
    """Execute a single tool call and return a ToolMessage."""
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_id = tool_call.get("id", tool_name)

    if tool_name not in tool_map:
        logger.warning("Unknown tool requested: %s", tool_name)
        result = f"Error: Tool '{tool_name}' not found."
    else:
        result = await _execute_with_retry(tool_map[tool_name], tool_args, config)

    return ToolMessage(content=result, tool_call_id=tool_id)


async def run_agent_with_tools(
    model,
    messages: list[BaseMessage],
    tools: Sequence[BaseTool],
    config: RunnableConfig | None = None,
    *,
    max_rounds: int = MAX_TOOL_ROUNDS,
    validate_fn: Callable[[str], str | None] | None = None,
    min_tool_calls: int = 0,
    max_reflections: int = 0,
    quality_criteria: list[str] | None = None,
) -> tuple[AIMessage, list[BaseMessage]]:
    """Run a model with tools in a loop until it produces a final text response.

    Args:
        model: The LangChain chat model (with tools already bound).
        messages: Initial messages (system + human).
        tools: The tool instances to execute.
        config: LangGraph RunnableConfig — pass this to propagate event callbacks
                so that on_tool_start/on_tool_end events appear in astream_events().
        max_rounds: Safety limit for tool call loops.
        validate_fn: Optional validation function. Receives the final response text.
                     Returns None if valid, or an error message string if invalid.
                     When invalid, the model is re-invoked once with a correction prompt.
        min_tool_calls: Minimum number of tool calls required before accepting a text
                        response. If the agent responds too early, it gets pushed back
                        to use more tools.

    Returns:
        A tuple of (final_ai_message, all_messages_including_tool_calls).
    """
    tool_map = {t.name: t for t in tools}
    all_messages = list(messages)
    total_tool_calls = 0

    for _ in range(max_rounds):
        response: AIMessage = await model.ainvoke(all_messages, config=config)
        all_messages.append(response)

        # If no tool calls, check min_tool_calls requirement
        if not response.tool_calls:
            if total_tool_calls < min_tool_calls and tools:
                tool_names = ", ".join(t.name for t in tools)
                pushback = HumanMessage(content=(
                    f"You haven't used enough tools yet ({total_tool_calls}/{min_tool_calls} required). "
                    f"Call more of these tools before responding: {tool_names}"
                ))
                all_messages.append(pushback)
                continue
            break

        # Execute all tool calls in parallel
        tool_tasks = [
            _execute_tool(tool_map, tool_call, config)
            for tool_call in response.tool_calls
        ]
        tool_messages = await asyncio.gather(*tool_tasks)
        all_messages.extend(tool_messages)
        total_tool_calls += len(response.tool_calls)
    else:
        # If we exhausted rounds, force a final text response
        logger.warning("Agent hit max tool rounds (%d), forcing final response", max_rounds)
        response = await model.ainvoke(all_messages, config=config)
        all_messages.append(response)

    # Reflection loop — self-critique and revision
    if max_reflections > 0 and quality_criteria and response.content:
        critique_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

        # Collect tool outputs so the critic can verify claims against source data
        tool_context_parts = []
        for msg in all_messages:
            if hasattr(msg, "type") and msg.type == "tool":
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                # Include tool name if available
                name = getattr(msg, "name", "tool")
                tool_context_parts.append(f"[{name}]: {content[:1500]}")
        tool_context = "\n\n".join(tool_context_parts[-6:])  # Last 6 tool results, capped

        for reflection_round in range(max_reflections):
            criteria_text = "\n".join(f"- {c}" for c in quality_criteria)
            critique_prompt = f"""You are a strict quality reviewer. Evaluate this agent output against the quality criteria below.

IMPORTANT: You have access to the SOURCE DATA the agent used (tool outputs). Use this to verify claims.
- If the agent claims a metric/number, check if it exists in the source data.
- If the agent claims to cite a source, check if that source appears in the tool outputs.
- If the agent adds information not present in any tool output, flag it as fabricated.

Quality criteria:
{criteria_text}

Source data (tool outputs):
{tool_context[:3000]}

Agent output:
{response.content[:4000]}

For each criterion, rate PASS or FAIL with a brief reason.
Flag any fabricated metrics, invented numbers, or unsourced claims as automatic FAIL.
End with VERDICT: PASS if all criteria pass, or VERDICT: FAIL if any fail.
If FAIL, provide specific revision instructions including what was fabricated and what the actual data shows."""

            critique = await critique_model.ainvoke([HumanMessage(content=critique_prompt)])

            logger.info(
                "Reflection round %d for agent: critique=%s",
                reflection_round + 1,
                "PASS" if "VERDICT: PASS" in critique.content else "FAIL",
            )

            if "VERDICT: PASS" in critique.content:
                break

            # Feed critique back to agent for revision
            revision_msg = HumanMessage(content=(
                f"[Reflection round {reflection_round + 1}] Your output needs revision:\n\n"
                f"{critique.content}\n\n"
                "Please revise your response addressing the critique above."
            ))
            all_messages.append(revision_msg)
            response = await model.ainvoke(all_messages, config=config)
            all_messages.append(response)
            # Drain any tool calls the model makes during revision
            for _drain in range(max_rounds):
                if not response.tool_calls:
                    break
                drain_tasks = [_execute_tool(tool_map, tc, config) for tc in response.tool_calls]
                drain_msgs = await asyncio.gather(*drain_tasks)
                all_messages.extend(drain_msgs)
                response = await model.ainvoke(all_messages, config=config)
                all_messages.append(response)

    # Output validation & self-correction
    if validate_fn and response.content:
        validation_error = validate_fn(response.content)
        if validation_error:
            logger.info("Validation failed: %s — re-invoking for correction", validation_error)
            correction_prompt = HumanMessage(content=(
                f"Your response did not pass validation: {validation_error}\n\n"
                "Please fix the issues and regenerate your response. "
                "Keep all the good parts, just address the specific problems noted."
            ))
            all_messages.append(correction_prompt)
            response = await model.ainvoke(all_messages, config=config)
            all_messages.append(response)
            # Drain any tool calls during validation correction
            for _drain in range(max_rounds):
                if not response.tool_calls:
                    break
                drain_tasks = [_execute_tool(tool_map, tc, config) for tc in response.tool_calls]
                drain_msgs = await asyncio.gather(*drain_tasks)
                all_messages.extend(drain_msgs)
                response = await model.ainvoke(all_messages, config=config)
                all_messages.append(response)

    return response, all_messages
